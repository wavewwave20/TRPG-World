"""
Phase 3: 서술 생성 노드

판정 결과를 바탕으로 스토리 서술을 생성합니다.
"""

import logging
import re
from typing import AsyncIterator

from langchain_core.prompts import ChatPromptTemplate
from langchain_litellm import ChatLiteLLM

from app.schemas import CharacterSheet, JudgmentOutcome, JudgmentResult
from app.utils.prompt_loader import load_prompt

logger = logging.getLogger("ai_gm.narrative_node")


def _select_recent_story_entries(story_history: list, limit: int | None = None) -> list:
    """스토리 히스토리를 시간순으로 정렬하여 반환합니다.

    story_history가 created_at을 가진 객체 목록이면 시간순(오래된 -> 최신)으로
    정렬합니다. limit이 지정되면 최신 limit개만 반환합니다.
    """
    if not story_history:
        return []

    entries = list(story_history)

    if all(hasattr(entry, "created_at") for entry in entries):
        entries.sort(key=lambda entry: (getattr(entry, "created_at") is None, getattr(entry, "created_at")))

    if limit is not None:
        return entries[-limit:]
    return entries


def _format_story_entry(entry: object) -> str:
    """스토리 항목을 프롬프트용 텍스트로 변환합니다."""
    if hasattr(entry, "role") and hasattr(entry, "content"):
        role = getattr(entry, "role", "") or "NARRATION"
        content = getattr(entry, "content", "") or ""
        return f"[{role}] {content}"

    if hasattr(entry, "content"):
        return str(getattr(entry, "content"))

    return str(entry)


def _extract_skill_names(skills: list[object], skill_type: str | None = None) -> list[str]:
    """스킬 목록에서 이름을 추출합니다.

    Args:
        skills: CharacterSheet.skills 원본 목록
        skill_type: "passive" | "active" 필터 (None이면 전체)
    """
    names: list[str] = []
    for skill in skills or []:
        if isinstance(skill, dict):
            raw_type = str(skill.get("type", "")).lower()
            if skill_type is not None and raw_type != skill_type:
                continue
            name = skill.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
        elif skill_type is None and isinstance(skill, str) and skill.strip():
            names.append(skill.strip())
    return names


def _extract_weakness_names(weaknesses: list[object]) -> list[str]:
    """약점 목록을 사람이 읽기 좋은 문자열로 변환합니다."""
    result: list[str] = []
    for weakness in weaknesses or []:
        if isinstance(weakness, str) and weakness.strip():
            result.append(weakness.strip())
            continue
        if isinstance(weakness, dict):
            name = weakness.get("name") or weakness.get("description")
            if isinstance(name, str) and name.strip():
                mitigation = weakness.get("mitigation")
                if isinstance(mitigation, int) and mitigation > 0:
                    result.append(f"{name.strip()} (완화 {mitigation}/3)")
                else:
                    result.append(name.strip())
    return result


def _extract_status_effect_names(status_effects: list[object]) -> list[str]:
    """상태 효과 목록에서 이름을 추출합니다."""
    result: list[str] = []
    for effect in status_effects or []:
        if isinstance(effect, str) and effect.strip():
            result.append(effect.strip())
            continue
        if isinstance(effect, dict):
            name = effect.get("name") or effect.get("description")
            if isinstance(name, str) and name.strip():
                result.append(name.strip())
    return result


def _format_character_context(characters: list[CharacterSheet]) -> str:
    """서술 프롬프트에 주입할 캐릭터 컨텍스트를 구성합니다."""
    lines: list[str] = []
    for char in characters:
        char_info = f"- **{char.name}** (ID: {char.id})"
        if char.race:
            char_info += f"\n  - 종족: {char.race}"
        if char.concept:
            char_info += f"\n  - 컨셉: {char.concept}"

        passive_skills = _extract_skill_names(char.skills, "passive")
        if passive_skills:
            char_info += f"\n  - 패시브: {', '.join(passive_skills)}"

        active_skills = _extract_skill_names(char.skills, "active")
        if active_skills:
            char_info += f"\n  - 액티브: {', '.join(active_skills)}"

        weakness_names = _extract_weakness_names(char.weaknesses)
        if weakness_names:
            char_info += f"\n  - 약점: {', '.join(weakness_names)}"

        status_names = _extract_status_effect_names(char.status_effects)
        if status_names:
            char_info += f"\n  - 상태 효과: {', '.join(status_names)}"

        lines.append(char_info)

    return "\n".join(lines)


async def generate_narrative(
    judgments: list[JudgmentResult],
    characters: list[CharacterSheet],
    world_context: str,
    story_history: list[str],
    llm_model: str = "gpt-4o",
    act_context: str | None = None,
    ai_summary: str | None = None,
    event_triggered: bool | None = None,
) -> str:
    """
    판정 결과를 바탕으로 스토리 서술을 생성합니다.

    이 함수는 Phase 3의 핵심 로직을 수행합니다:
    1. 모든 판정 결과를 통합
    2. AI를 사용하여 몰입감 있는 서술 생성

    Args:
        judgments: 판정 결과 목록
        characters: 캐릭터 정보 목록
        world_context: 세계관 설정
        story_history: 최근 스토리 히스토리
        llm_model: 사용할 LLM 모델

    Returns:
        str: 생성된 서술 텍스트

    Raises:
        ValueError: AI 호출 실패 시
    """
    logger.info(f"Generating narrative for {len(judgments)} judgments")

    # 프롬프트 로드
    system_message = load_prompt("narrative_prompt.md")

    # 컨텍스트 정보 구성
    context_parts = []

    # 현재 막 정보
    if act_context:
        context_parts.append(f"## 현재 스토리 진행\n\n{act_context}")

    # 랜덤 이벤트 지시 (act_context 바로 뒤, 세계관 앞)
    if event_triggered is not None:
        from app.services.event_probability import build_event_context_instruction

        context_parts.append(build_event_context_instruction(event_triggered))

    # 세계관 정보
    if world_context:
        context_parts.append(f"## 세계관\n\n{world_context}")

    # 장기 요약 (Act 종료 시점에만 갱신되는 누적 요약)
    if ai_summary:
        context_parts.append(f"## 장기 요약\n\n{ai_summary}")

    # 캐릭터 정보
    char_map = {char.id: char for char in characters}
    context_parts.append("## 캐릭터 정보\n\n" + _format_character_context(characters))

    # 스토리 히스토리 (현재 막 전체 — 이전 막은 ai_summary로 압축됨)
    sorted_history = _select_recent_story_entries(story_history)
    if sorted_history:
        history_text = "\n\n".join(_format_story_entry(entry) for entry in sorted_history)
        context_parts.append(f"## 현재 막 스토리\n\n{history_text}")

    # 판정 결과
    judgment_list = []
    for i, judgment in enumerate(judgments, 1):
        character = char_map.get(judgment.character_id)
        char_name = character.name if character else f"캐릭터 {judgment.character_id}"

        if judgment.outcome == JudgmentOutcome.AUTO_SUCCESS:
            judgment_text = (
                f"{i}. **{char_name}**\n"
                f"   - 행동: {judgment.action_text}\n"
                f"   - 결과: 자동 성공 (위험이 없는 행동)"
            )
        else:
            judgment_text = (
                f"{i}. **{char_name}**\n"
                f"   - 행동: {judgment.action_text}\n"
                f"   - 주사위: {judgment.dice_result}\n"
                f"   - 보정치: {judgment.modifier:+d}\n"
                f"   - 최종값: {judgment.final_value}\n"
                f"   - 난이도: {judgment.difficulty}\n"
                f"   - 결과: {_get_outcome_korean(judgment.outcome.value)}\n"
                f"   - 설명: {judgment.outcome_reasoning}"
            )
        judgment_list.append(judgment_text)
    context_parts.append("## 판정 결과\n\n" + "\n\n".join(judgment_list))

    context_text = "\n\n".join(context_parts)

    # ChatPromptTemplate 구성
    chat_template = ChatPromptTemplate.from_messages(
        [
            system_message,
            (
                "human",
                "{context}\n\n위 판정 결과들을 바탕으로 몰입감 있는 스토리를 서술해주세요.\n"
                "응답은 반드시 첫 글자부터 <story>로 시작하고 마지막을 </summary>로 끝내세요. "
                "설명 문장, 코드블록, 머리말/꼬리말은 절대 추가하지 마세요.",
            ),
        ]
    )

    llm = ChatLiteLLM(
        model=llm_model,
        temperature=1.0,
        max_tokens=4000,
    )

    # Chain 구성 및 실행
    chain = chat_template | llm

    try:
        response = await chain.ainvoke({"context": context_text})
        narrative = response.content.strip()

        logger.info(f"Generated narrative: {len(narrative)} characters")
        logger.debug(f"Narrative preview: {narrative[:200]}...")

        return narrative

    except Exception as e:
        logger.error(f"AI call failed: {e}", exc_info=True)
        raise ValueError(f"서술 생성 실패: {e!s}") from e


def _get_outcome_korean(outcome: str) -> str:
    """
    판정 결과를 한국어로 변환합니다.

    Args:
        outcome: 영문 판정 결과

    Returns:
        str: 한국어 판정 결과
    """
    outcome_map = {
        "critical_success": "대성공",
        "success": "성공",
        "failure": "실패",
        "critical_failure": "대실패",
        "auto_success": "자동 성공",
    }
    return outcome_map.get(outcome, outcome)


async def generate_narrative_streaming(
    judgments: list[JudgmentResult],
    characters: list[CharacterSheet],
    world_context: str,
    story_history: list[str],
    llm_model: str = "gemini/gemini-3-pro-preview",
    act_context: str | None = None,
    ai_summary: str | None = None,
    event_triggered: bool | None = None,
) -> AsyncIterator[str]:
    """
    판정 결과를 바탕으로 스토리 서술을 스트리밍으로 생성합니다.

    이 함수는 LLM의 스트리밍 API를 사용하여 토큰을 하나씩 yield합니다.
    각 토큰은 버퍼에 저장되어 나중에 클라이언트로 재생됩니다.

    Args:
        judgments: 판정 결과 목록
        characters: 캐릭터 정보 목록
        world_context: 세계관 설정
        story_history: 최근 스토리 히스토리
        llm_model: 사용할 LLM 모델
        act_context: 현재 막 정보
        ai_summary: 장기 요약

    Yields:
        str: LLM에서 생성된 텍스트 토큰

    Raises:
        ValueError: AI 호출 실패 시

    Requirements: 7.1, 7.2, 7.5
    """
    logger.info(f"Generating narrative (streaming) for {len(judgments)} judgments")

    # 프롬프트 로드
    system_message = load_prompt("narrative_prompt.md")

    # 컨텍스트 정보 구성 (기존 로직과 동일)
    context_parts = []

    # 현재 막 정보
    if act_context:
        context_parts.append(f"## 현재 스토리 진행\n\n{act_context}")

    # 랜덤 이벤트 지시 (act_context 바로 뒤, 세계관 앞)
    if event_triggered is not None:
        from app.services.event_probability import build_event_context_instruction

        context_parts.append(build_event_context_instruction(event_triggered))

    # 세계관 정보
    if world_context:
        context_parts.append(f"## 세계관\n\n{world_context}")

    # 장기 요약 (Act 종료 시점에만 갱신되는 누적 요약)
    if ai_summary:
        context_parts.append(f"## 장기 요약\n\n{ai_summary}")

    # 캐릭터 정보
    char_map = {char.id: char for char in characters}
    context_parts.append("## 캐릭터 정보\n\n" + _format_character_context(characters))

    # 스토리 히스토리 (현재 막 전체 — 이전 막은 ai_summary로 압축됨)
    sorted_history = _select_recent_story_entries(story_history)
    if sorted_history:
        history_text = "\n\n".join(_format_story_entry(entry) for entry in sorted_history)
        context_parts.append(f"## 최근 스토리\n\n{history_text}")

    # 판정 결과
    judgment_list = []
    for i, judgment in enumerate(judgments, 1):
        character = char_map.get(judgment.character_id)
        char_name = character.name if character else f"캐릭터 {judgment.character_id}"

        if judgment.outcome == JudgmentOutcome.AUTO_SUCCESS:
            judgment_text = (
                f"{i}. **{char_name}**\n"
                f"   - 행동: {judgment.action_text}\n"
                f"   - 결과: 자동 성공 (위험이 없는 행동)"
            )
        else:
            judgment_text = (
                f"{i}. **{char_name}**\n"
                f"   - 행동: {judgment.action_text}\n"
                f"   - 주사위: {judgment.dice_result}\n"
                f"   - 보정치: {judgment.modifier:+d}\n"
                f"   - 최종값: {judgment.final_value}\n"
                f"   - 난이도: {judgment.difficulty}\n"
                f"   - 결과: {_get_outcome_korean(judgment.outcome.value)}\n"
                f"   - 설명: {judgment.outcome_reasoning}"
            )
        judgment_list.append(judgment_text)
    context_parts.append("## 판정 결과\n\n" + "\n\n".join(judgment_list))

    context_text = "\n\n".join(context_parts)

    # ChatPromptTemplate 구성
    chat_template = ChatPromptTemplate.from_messages(
        [
            system_message,
            (
                "human",
                "{context}\n\n위 판정 결과들을 바탕으로 몰입감 있는 스토리를 서술해주세요.\n"
                "응답은 반드시 첫 글자부터 <story>로 시작하고 마지막을 </summary>로 끝내세요. "
                "설명 문장, 코드블록, 머리말/꼬리말은 절대 추가하지 마세요.",
            ),
        ]
    )

    llm = ChatLiteLLM(
        model=llm_model,
        temperature=1.0,
        max_tokens=4000,
    )

    # Chain 구성
    chain = chat_template | llm

    try:
        # 스트리밍 호출
        token_count = 0
        async for chunk in chain.astream({"context": context_text}):
            # chunk.content에 토큰이 들어있음
            if hasattr(chunk, "content") and chunk.content:
                token = chunk.content
                yield token
                token_count += 1

        logger.info(f"Streaming complete: {token_count} tokens generated")

    except Exception as e:
        logger.error(f"AI streaming failed: {e}", exc_info=True)
        raise ValueError(f"서술 스트리밍 실패: {e!s}") from e


def parse_narrative_xml(raw_text: str) -> tuple[str, dict]:
    """AI 응답에서 <story>와 <summary> XML 태그를 파싱합니다.

    Expected format:
        <story>
        [서술 텍스트]
        </story>
        <summary>
        <situation>현재 상황 한줄 요약</situation>
        <act_transition>true/false</act_transition>
        <new_act_title>새 막 제목</new_act_title>
        <new_act_subtitle>부제</new_act_subtitle>
        </summary>

    태그가 없으면 fallback: 전체 텍스트를 서술로, transition=false.

    Args:
        raw_text: LLM의 원본 응답 텍스트

    Returns:
        (narrative, metadata) 튜플
        - narrative: 클린 서술 텍스트
        - metadata: {"situation", "act_transition", "new_act_title", "new_act_subtitle"}
    """
    # <story> 태그 추출
    story_match = re.search(r"<story>(.*?)</story>", raw_text, re.DOTALL)

    if story_match:
        narrative = story_match.group(1).strip()
    else:
        # fallback: <summary> 태그 이전의 모든 텍스트를 서술로 사용
        summary_start = raw_text.find("<summary>")
        if summary_start != -1:
            narrative = raw_text[:summary_start].strip()
        else:
            narrative = raw_text.strip()

    # <summary> 메타데이터 파싱
    metadata = {
        "situation": "",
        "act_transition": False,
        "new_act_title": None,
        "new_act_subtitle": None,
    }

    summary_match = re.search(r"<summary>(.*?)</summary>", raw_text, re.DOTALL)
    if summary_match:
        summary_block = summary_match.group(1)

        situation_match = re.search(r"<situation>(.*?)</situation>", summary_block, re.DOTALL)
        if situation_match:
            metadata["situation"] = situation_match.group(1).strip()

        transition_match = re.search(r"<act_transition>(.*?)</act_transition>", summary_block, re.DOTALL)
        if transition_match:
            val = transition_match.group(1).strip().lower()
            metadata["act_transition"] = val in ("true", "yes", "1")

        title_match = re.search(r"<new_act_title>(.*?)</new_act_title>", summary_block, re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
            if title and title.lower() not in ("null", "none", ""):
                metadata["new_act_title"] = title

        subtitle_match = re.search(r"<new_act_subtitle>(.*?)</new_act_subtitle>", summary_block, re.DOTALL)
        if subtitle_match:
            subtitle = subtitle_match.group(1).strip()
            if subtitle and subtitle.lower() not in ("null", "none", ""):
                metadata["new_act_subtitle"] = subtitle
    else:
        logger.warning("XML <summary> 태그 없음, fallback: act_transition=false")

    # act_transition이 true인데 제목이 없으면 강제 false
    if metadata["act_transition"] and not metadata["new_act_title"]:
        logger.warning("act_transition=true이지만 new_act_title 없음, 전환 거부")
        metadata["act_transition"] = False

    logger.info(
        f"XML 파싱 완료: narrative={len(narrative)}자, "
        f"transition={metadata['act_transition']}, "
        f"situation='{metadata['situation'][:50]}'"
    )

    return narrative, metadata
