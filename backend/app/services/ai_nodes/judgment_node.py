"""
Phase 1: 행동 판정 노드

플레이어 행동을 분석하고 난이도(DC)를 결정합니다.
"""

import json
import logging
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_litellm import ChatLiteLLM

from app.schemas import ActionAnalysis, ActionType, CharacterSheet, PlayerAction
from app.utils.prompt_loader import load_prompt

logger = logging.getLogger("ai_gm.judgment_node")


async def analyze_and_judge_actions(
    player_actions: list[PlayerAction],
    characters: list[CharacterSheet],
    world_context: str,
    story_history: list[str],
    llm_model: str = "gpt-4o",
) -> list[ActionAnalysis]:
    """
    플레이어 행동을 분석하고 보정치와 난이도를 결정합니다.

    이 함수는 Phase 1의 핵심 로직을 수행합니다:
    1. 캐릭터 스탯에서 보정치 계산
    2. AI를 사용하여 난이도(DC) 결정

    Args:
        player_actions: 분석할 플레이어 행동 목록
        characters: 캐릭터 정보 목록
        world_context: 세계관 설정
        story_history: 최근 스토리 히스토리
        llm_model: 사용할 LLM 모델

    Returns:
        List[ActionAnalysis]: 각 행동에 대한 분석 결과 (보정치 + DC)

    Raises:
        ValueError: AI 호출 실패 또는 응답 파싱 실패 시
    """
    logger.info(f"Analyzing {len(player_actions)} actions")

    # 캐릭터 ID로 빠른 조회를 위한 맵 생성
    char_map = {char.id: char for char in characters}

    # 1단계: 보정치 계산
    analyses = []
    for action in player_actions:
        character = char_map.get(action.character_id)
        if not character:
            logger.warning(f"Character {action.character_id} not found, skipping")
            continue

        # 능력치에서 보정치 계산
        modifier = _calculate_modifier(character, action.action_type)

        # 분석 객체 생성 (DC는 아직 미정)
        analysis = ActionAnalysis(
            character_id=action.character_id,
            action_text=action.action_text,
            action_type=action.action_type,
            modifier=modifier,
            difficulty=15,  # 기본값, AI가 결정할 예정
            difficulty_reasoning="",
        )
        analyses.append(analysis)

        logger.debug(f"Character {action.character_id}: {action.action_type.value} modifier={modifier:+d}")

    if not analyses:
        raise ValueError("No valid actions to analyze")

    # 2단계: AI를 사용하여 난이도 결정
    try:
        dc_results = await _determine_difficulty_with_ai(
            player_actions=player_actions,
            characters=characters,
            world_context=world_context,
            story_history=story_history,
            llm_model=llm_model,
        )

        # 분석 결과에 DC 적용
        for analysis in analyses:
            dc_info = dc_results.get(analysis.character_id, {})
            analysis.difficulty = dc_info.get("difficulty", 15)
            analysis.difficulty_reasoning = dc_info.get("reasoning", "기본 난이도 적용")

            # DC 범위 검증 (5-30)
            analysis.difficulty = max(5, min(30, analysis.difficulty))

            logger.info(f"Character {analysis.character_id}: DC={analysis.difficulty}, modifier={analysis.modifier:+d}")

    except Exception as e:
        logger.error(f"Failed to determine difficulty with AI: {e}")
        # AI 실패 시 기본 DC 사용
        for analysis in analyses:
            analysis.difficulty = 15
            analysis.difficulty_reasoning = f"기본 난이도 적용 (AI 오류: {e!s})"

    return analyses


def _calculate_modifier(character: CharacterSheet, action_type: ActionType) -> int:
    """
    캐릭터 능력치에서 보정치를 계산합니다.

    보정치 = (능력치 - 10) // 2

    Args:
        character: 캐릭터 정보
        action_type: 행동 유형 (어떤 능력치를 사용할지 결정)

    Returns:
        int: 계산된 보정치
    """
    ability_map = {
        ActionType.STRENGTH: character.strength,
        ActionType.DEXTERITY: character.dexterity,
        ActionType.CONSTITUTION: character.constitution,
        ActionType.INTELLIGENCE: character.intelligence,
        ActionType.WISDOM: character.wisdom,
        ActionType.CHARISMA: character.charisma,
    }

    ability_score = ability_map.get(action_type, 10)
    modifier = (ability_score - 10) // 2

    return modifier


async def _determine_difficulty_with_ai(
    player_actions: list[PlayerAction],
    characters: list[CharacterSheet],
    world_context: str,
    story_history: list[str],
    llm_model: str,
) -> dict[int, dict[str, Any]]:
    """
    AI를 사용하여 각 행동의 난이도(DC)를 결정합니다.

    Args:
        player_actions: 플레이어 행동 목록
        characters: 캐릭터 정보 목록
        world_context: 세계관 설정
        story_history: 스토리 히스토리
        llm_model: LLM 모델명

    Returns:
        Dict[int, Dict[str, Any]]: character_id를 키로 하는 DC 정보
            {"difficulty": int, "reasoning": str}

    Raises:
        ValueError: AI 호출 실패 시
    """
    logger.debug("Calling AI to determine difficulty")

    # 프롬프트 로드
    system_message = load_prompt("judgment_prompt.md")

    # 컨텍스트 정보 구성
    context_parts = []

    # 세계관 정보
    if world_context:
        context_parts.append(f"## 세계관\n\n{world_context}")

    # 캐릭터 정보
    char_info_list = []
    for char in characters:
        char_info = (
            f"- **{char.name}** (ID: {char.id})\n"
            f"  - 근력: {char.strength}, 민첩: {char.dexterity}, 건강: {char.constitution}\n"
            f"  - 지능: {char.intelligence}, 지혜: {char.wisdom}, 매력: {char.charisma}"
        )
        char_info_list.append(char_info)
    context_parts.append("## 캐릭터 정보\n\n" + "\n".join(char_info_list))

    # 스토리 히스토리 (최근 5개만)
    if story_history:
        recent_history = story_history[-5:]
        # StoryLogEntry 객체를 문자열로 변환
        history_texts = []
        for entry in recent_history:
            if hasattr(entry, "content") and entry.content:
                history_texts.append(str(entry.content))
            elif isinstance(entry, str):
                history_texts.append(entry)
            elif entry is not None:
                history_texts.append(str(entry))
        if history_texts:
            history_text = "\n\n".join(history_texts)
            context_parts.append(f"## 최근 스토리\n\n{history_text}")

    # 행동 정보
    action_list = []
    for i, action in enumerate(player_actions, 1):
        action_text = (
            f"{i}. **캐릭터 ID {action.character_id}**\n"
            f"   행동: {action.action_text}\n"
            f"   행동 유형: {action.action_type.value}"
        )
        action_list.append(action_text)
    context_parts.append("## 분석할 행동\n\n" + "\n\n".join(action_list))

    context_text = "\n\n".join(context_parts)

    # ChatPromptTemplate 구성
    chat_template = ChatPromptTemplate.from_messages(
        [
            system_message,
            ("human", "{context}\n\n위 행동들을 분석하고 각각의 난이도(DC)를 결정해주세요."),
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
        response_text = response.content

        logger.debug(f"AI response: {response_text[:200]}...")

        # JSON 응답 파싱
        dc_results = _parse_dc_response(response_text)

        return dc_results

    except Exception as e:
        logger.error(f"AI call failed: {e}", exc_info=True)
        raise ValueError(f"AI 호출 실패: {e!s}") from e


def _parse_dc_response(response_text: str) -> dict[int, dict[str, Any]]:
    """
    AI 응답에서 DC 정보를 파싱합니다.

    예상 형식:
    [
        {
            "character_id": 1,
            "action_type": "dexterity",
            "difficulty": 15,
            "difficulty_reasoning": "..."
        },
        ...
    ]

    Args:
        response_text: AI 응답 텍스트

    Returns:
        Dict[int, Dict[str, Any]]: character_id를 키로 하는 DC 정보
    """
    try:
        # 마크다운 코드 블록 제거
        text = response_text.strip()
        if "```" in text:
            text = text.replace("```json", "").replace("```", "").strip()

        # JSON 배열 추출
        start_idx = text.find("[")
        end_idx = text.rfind("]") + 1

        if start_idx == -1 or end_idx == 0:
            logger.warning(f"No JSON array found in response: {text[:200]}")
            return {}

        json_text = text[start_idx:end_idx]
        results = json.loads(json_text)

        # character_id를 키로 하는 딕셔너리로 변환
        dc_map = {}
        for item in results:
            char_id = item.get("character_id")
            if char_id is not None:
                dc_map[char_id] = {
                    "difficulty": item.get("difficulty", 15),
                    "reasoning": (item.get("reasoning", "") or item.get("difficulty_reasoning", "")),
                }

        logger.info(f"Successfully parsed {len(dc_map)} DC results")
        return dc_map

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        logger.error(f"Problematic text: {text[:500]}")
        return {}
    except Exception as e:
        logger.error(f"Error parsing DC response: {e}")
        return {}
