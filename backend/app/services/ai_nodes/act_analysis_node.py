"""스토리 막(Act) 전환 분석 및 성장 보상 생성 AI 노드."""

import json
import logging

from langchain_litellm import ChatLiteLLM
from langchain_core.prompts import ChatPromptTemplate

from app.schemas import (
    ActTransitionAnalysis,
    CharacterSheet,
    GrowthReward,
    StoryActInfo,
    StoryLogEntry,
)
from app.utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


async def analyze_act_transition(
    world_context: str,
    current_act: StoryActInfo,
    story_history: list[StoryLogEntry],
    characters: list[CharacterSheet],
    llm_model: str = "gpt-4o",
) -> ActTransitionAnalysis:
    """현재 막의 전환 여부를 분석합니다.

    서술 완료 후 호출되며, AI가 스토리에서 사건을 식별하고
    충분한 사건(3개 이상)이 발생했는지 판단합니다.

    Args:
        world_context: 세계관 설정
        current_act: 현재 진행 중인 막 정보
        story_history: 현재 막의 스토리 로그
        characters: 캐릭터 정보 목록
        llm_model: 사용할 LLM 모델

    Returns:
        ActTransitionAnalysis: 전환 분석 결과
    """
    logger.info(
        f"막 전환 분석 시작: {current_act.act_number}막 '{current_act.title}', "
        f"스토리 {len(story_history)}개"
    )

    system_message = load_prompt("act_analysis_prompt.md")

    # 컨텍스트 구성
    context_parts = []

    if world_context:
        context_parts.append(f"## 세계관\n\n{world_context}")

    # 현재 막 정보
    act_info = f"## 현재 막\n\n{current_act.act_number}막 — {current_act.title}"
    if current_act.subtitle:
        act_info += f": {current_act.subtitle}"
    context_parts.append(act_info)

    # 캐릭터 정보
    char_info_list = []
    for char in characters:
        info = f"- **{char.name}** (ID: {char.id})"
        if char.concept:
            info += f" — {char.concept}"
        char_info_list.append(info)
    context_parts.append("## 캐릭터\n\n" + "\n".join(char_info_list))

    # 현재 막의 스토리
    if story_history:
        history_texts = []
        for entry in story_history:
            prefix = "[서술]" if entry.role == "AI" else "[행동]"
            history_texts.append(f"{prefix} {entry.content}")
        context_parts.append("## 현재 막의 스토리\n\n" + "\n\n".join(history_texts))

    context_text = "\n\n".join(context_parts)

    chat_template = ChatPromptTemplate.from_messages(
        [
            system_message,
            (
                "human",
                "{context}\n\n"
                "위 스토리를 분석하여 막 전환 여부를 JSON으로 응답해주세요.",
            ),
        ]
    )

    llm = ChatLiteLLM(
        model=llm_model,
        temperature=0.3,
        max_tokens=1000,
    )

    chain = chat_template | llm

    try:
        response = await chain.ainvoke({"context": context_text})
        result = _parse_act_analysis(response.content.strip())

        # 코드 레벨 검증: 사건 수 ≤ 2이면 강제로 전환 불가
        if result.event_count <= 2:
            result.should_transition = False
            result.new_act_title = None
            result.new_act_subtitle = None

        logger.info(
            f"막 전환 분석 완료: 사건 {result.event_count}개, "
            f"전환={'예' if result.should_transition else '아니오'}"
        )
        return result

    except Exception as e:
        logger.error(f"막 전환 분석 실패: {e}", exc_info=True)
        # 실패 시 전환하지 않음
        return ActTransitionAnalysis(
            identified_events=[],
            event_count=0,
            should_transition=False,
            reasoning=f"분석 실패: {e!s}",
        )


async def generate_act_title(
    world_context: str,
    narrative_text: str,
    llm_model: str = "gpt-4o",
) -> dict[str, str | None]:
    """게임 시작 시 Act 1의 제목과 부제를 생성합니다.

    Args:
        world_context: 세계관 설정
        narrative_text: 오프닝 서술 텍스트
        llm_model: 사용할 LLM 모델

    Returns:
        dict: {"title": "제목", "subtitle": "부제"}
    """
    logger.info("Act 1 제목 생성 시작")

    chat_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "당신은 TRPG 게임의 서사 구조 보조입니다.\n"
                "세계관과 오프닝 서술을 바탕으로 1막의 제목과 부제를 생성합니다.\n\n"
                "## 지침\n"
                "- 제목: 간결하고 상징적 (예: '어둠의 전조', '잊혀진 맹세')\n"
                "- 부제: 구체적인 상황 설명 (예: '폐광산의 비밀', '왕도로의 여정')\n"
                "- 한국어로 작성\n\n"
                '반드시 JSON으로만 응답: {{"title": "...", "subtitle": "..."}}',
            ),
            (
                "human",
                "## 세계관\n\n{world_context}\n\n"
                "## 오프닝 서술\n\n{narrative}\n\n"
                "1막의 제목과 부제를 생성해주세요.",
            ),
        ]
    )

    llm = ChatLiteLLM(
        model=llm_model,
        temperature=0.7,
        max_tokens=200,
    )

    chain = chat_template | llm

    try:
        response = await chain.ainvoke(
            {"world_context": world_context, "narrative": narrative_text}
        )
        data = _extract_json(response.content.strip())
        title = data.get("title", "1막")
        subtitle = data.get("subtitle")
        logger.info(f"Act 1 제목 생성 완료: '{title}' — '{subtitle}'")
        return {"title": title, "subtitle": subtitle}

    except Exception as e:
        logger.error(f"Act 1 제목 생성 실패: {e}", exc_info=True)
        return {"title": "서막", "subtitle": None}


async def generate_growth_rewards(
    world_context: str,
    characters: list[CharacterSheet],
    act_story_entries: list[StoryLogEntry],
    act_info: StoryActInfo,
    llm_model: str = "gpt-4o",
) -> list[GrowthReward]:
    """막 종료 시 캐릭터별 성장 보상을 생성합니다.

    Args:
        world_context: 세계관 설정
        characters: 캐릭터 정보 목록
        act_story_entries: 종료되는 막의 전체 스토리 로그
        act_info: 종료되는 막 정보
        llm_model: 사용할 LLM 모델

    Returns:
        list[GrowthReward]: 캐릭터별 성장 보상 목록
    """
    logger.info(
        f"성장 보상 생성 시작: {act_info.act_number}막 '{act_info.title}', "
        f"캐릭터 {len(characters)}명"
    )

    system_message = load_prompt("growth_reward_prompt.md")

    # 컨텍스트 구성
    context_parts = []

    if world_context:
        context_parts.append(f"## 세계관\n\n{world_context}")

    # 막 정보
    act_text = f"## 완료된 막\n\n{act_info.act_number}막 — {act_info.title}"
    if act_info.subtitle:
        act_text += f": {act_info.subtitle}"
    context_parts.append(act_text)

    # 캐릭터 상세 정보
    char_details = []
    for char in characters:
        detail = f"### {char.name} (ID: {char.id})\n"
        detail += f"- 능력치: STR {char.strength}, DEX {char.dexterity}, CON {char.constitution}, INT {char.intelligence}, WIS {char.wisdom}, CHA {char.charisma}\n"
        if char.skills:
            skill_names = [s.get("name", "?") for s in char.skills]
            detail += f"- 스킬: {', '.join(skill_names)}\n"
        if char.weaknesses:
            weakness_names = []
            for w in char.weaknesses:
                if isinstance(w, dict):
                    name = w.get("name", str(w))
                    mitigation = w.get("mitigation", 0)
                    weakness_names.append(f"{name} (완화: {mitigation}/3)")
                else:
                    weakness_names.append(str(w))
            detail += f"- 약점: {', '.join(weakness_names)}\n"
        char_details.append(detail)
    context_parts.append("## 캐릭터\n\n" + "\n".join(char_details))

    # 막의 스토리
    if act_story_entries:
        story_texts = []
        for entry in act_story_entries:
            prefix = "[서술]" if entry.role == "AI" else "[행동]"
            story_texts.append(f"{prefix} {entry.content}")
        context_parts.append("## 이번 막의 스토리\n\n" + "\n\n".join(story_texts))

    context_text = "\n\n".join(context_parts)

    chat_template = ChatPromptTemplate.from_messages(
        [
            system_message,
            (
                "human",
                "{context}\n\n"
                "위 스토리를 바탕으로 각 캐릭터의 성장 보상을 JSON 배열로 응답해주세요.",
            ),
        ]
    )

    llm = ChatLiteLLM(
        model=llm_model,
        temperature=0.7,
        max_tokens=2000,
    )

    chain = chat_template | llm

    try:
        response = await chain.ainvoke({"context": context_text})
        rewards = _parse_growth_rewards(response.content.strip(), characters)

        logger.info(f"성장 보상 생성 완료: {len(rewards)}개")
        return rewards

    except Exception as e:
        logger.error(f"성장 보상 생성 실패: {e}", exc_info=True)
        return []


def _parse_act_analysis(response_text: str) -> ActTransitionAnalysis:
    """AI 응답에서 막 전환 분석을 파싱합니다."""
    data = _extract_json(response_text)

    return ActTransitionAnalysis(
        identified_events=data.get("identified_events", []),
        event_count=data.get("event_count", len(data.get("identified_events", []))),
        should_transition=data.get("should_transition", False),
        reasoning=data.get("reasoning", ""),
        new_act_title=data.get("new_act_title"),
        new_act_subtitle=data.get("new_act_subtitle"),
    )


def _parse_growth_rewards(
    response_text: str, characters: list[CharacterSheet]
) -> list[GrowthReward]:
    """AI 응답에서 성장 보상을 파싱합니다."""
    data = _extract_json(response_text)

    # JSON 배열이 아닌 경우 처리
    if isinstance(data, dict):
        data = data.get("rewards", [data])

    valid_char_ids = {c.id for c in characters}
    char_name_map = {c.id: c.name for c in characters}
    rewards = []

    for item in data:
        char_id = item.get("character_id")
        if char_id not in valid_char_ids:
            logger.warning(f"잘못된 character_id: {char_id}, 스킵")
            continue

        growth_type = item.get("growth_type", "")
        if growth_type not in ("ability_increase", "new_skill", "weakness_mitigated"):
            logger.warning(f"잘못된 growth_type: {growth_type}, 스킵")
            continue

        rewards.append(
            GrowthReward(
                character_id=char_id,
                character_name=item.get("character_name", ""),
                growth_type=growth_type,
                growth_detail=item.get("growth_detail", {}),
                narrative_reason=item.get("narrative_reason", ""),
            )
        )

    # Fallback: 모든 캐릭터에 최소 1개 ability_increase 보장
    chars_with_reward = {r.character_id for r in rewards if r.growth_type == "ability_increase"}
    for char in characters:
        if char.id not in chars_with_reward:
            logger.warning(f"캐릭터 {char.name}(ID:{char.id})에 ability_increase 없음, fallback 추가")
            rewards.append(
                GrowthReward(
                    character_id=char.id,
                    character_name=char_name_map.get(char.id, ""),
                    growth_type="ability_increase",
                    growth_detail={"ability": "constitution", "delta": 1},
                    narrative_reason=f"{char_name_map.get(char.id, '모험가')}는 이번 막의 여정을 통해 한층 단련되었다.",
                )
            )

    return rewards


def _extract_json(text: str) -> dict | list:
    """텍스트에서 JSON을 추출합니다. 마크다운 코드블록도 처리."""
    # 마크다운 코드블록 제거
    if "```json" in text:
        text = text.split("```json", 1)[1]
        text = text.split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1]
        text = text.split("```", 1)[0]

    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # JSON 부분만 추출 시도
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start = text.find(start_char)
            end = text.rfind(end_char)
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    continue

        logger.error(f"JSON 파싱 실패: {text[:200]}")
        raise ValueError(f"JSON 파싱 실패: {text[:200]}")
