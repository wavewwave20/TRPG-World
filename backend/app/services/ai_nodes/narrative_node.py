"""
Phase 3: 서술 생성 노드

판정 결과를 바탕으로 스토리 서술을 생성합니다.
"""

import logging
from typing import AsyncIterator

from langchain_core.prompts import ChatPromptTemplate
from langchain_litellm import ChatLiteLLM

from app.schemas import CharacterSheet, JudgmentResult
from app.utils.prompt_loader import load_prompt

logger = logging.getLogger("ai_gm.narrative_node")


async def generate_narrative(
    judgments: list[JudgmentResult],
    characters: list[CharacterSheet],
    world_context: str,
    story_history: list[str],
    llm_model: str = "gpt-4o",
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

    # 세계관 정보
    if world_context:
        context_parts.append(f"## 세계관\n\n{world_context}")

    # 캐릭터 정보
    char_map = {char.id: char for char in characters}
    char_info_list = []
    for char in characters:
        char_info = f"- **{char.name}** (ID: {char.id})"
        if char.race:
            char_info += f"\n  - 종족: {char.race}"
        if char.concept:
            char_info += f"\n  - 컨셉: {char.concept}"
        char_info_list.append(char_info)
    context_parts.append("## 캐릭터 정보\n\n" + "\n".join(char_info_list))

    # 스토리 히스토리 (최근 5개만)
    if story_history:
        recent_history = story_history[-5:]
        # StoryLogEntry 객체를 문자열로 변환
        history_texts = []
        for entry in recent_history:
            if hasattr(entry, "content"):
                history_texts.append(entry.content)
            else:
                history_texts.append(str(entry))
        history_text = "\n\n".join(history_texts)
        context_parts.append(f"## 최근 스토리\n\n{history_text}")

    # 판정 결과
    judgment_list = []
    for i, judgment in enumerate(judgments, 1):
        character = char_map.get(judgment.character_id)
        char_name = character.name if character else f"캐릭터 {judgment.character_id}"

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
            ("human", "{context}\n\n위 판정 결과들을 바탕으로 몰입감 있는 스토리를 서술해주세요."),
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
    }
    return outcome_map.get(outcome, outcome)


async def generate_narrative_streaming(
    judgments: list[JudgmentResult],
    characters: list[CharacterSheet],
    world_context: str,
    story_history: list[str],
    llm_model: str = "gpt-4o",
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
    
    # 세계관 정보
    if world_context:
        context_parts.append(f"## 세계관\n\n{world_context}")
    
    # 캐릭터 정보
    char_map = {char.id: char for char in characters}
    char_info_list = []
    for char in characters:
        char_info = f"- **{char.name}** (ID: {char.id})"
        if char.race:
            char_info += f"\n  - 종족: {char.race}"
        if char.concept:
            char_info += f"\n  - 컨셉: {char.concept}"
        char_info_list.append(char_info)
    context_parts.append("## 캐릭터 정보\n\n" + "\n".join(char_info_list))
    
    # 스토리 히스토리 (최근 5개만)
    if story_history:
        recent_history = story_history[-5:]
        history_texts = []
        for entry in recent_history:
            if hasattr(entry, "content"):
                history_texts.append(entry.content)
            else:
                history_texts.append(str(entry))
        history_text = "\n\n".join(history_texts)
        context_parts.append(f"## 최근 스토리\n\n{history_text}")
    
    # 판정 결과
    judgment_list = []
    for i, judgment in enumerate(judgments, 1):
        character = char_map.get(judgment.character_id)
        char_name = character.name if character else f"캐릭터 {judgment.character_id}"
        
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
            ("human", "{context}\n\n위 판정 결과들을 바탕으로 몰입감 있는 스토리를 서술해주세요."),
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

