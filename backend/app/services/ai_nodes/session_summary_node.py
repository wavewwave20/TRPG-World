"""
Act 종료 시점의 장기 요약 생성 노드.

세션의 이전 ai_summary와 방금 끝난 Act 로그를 합쳐,
다음 Act에서 참조할 수 있는 압축 요약을 생성합니다.
"""

import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_litellm import ChatLiteLLM

from app.schemas import GrowthReward, StoryActInfo, StoryLogEntry

logger = logging.getLogger("ai_gm.session_summary_node")


def _format_story_entry(entry: StoryLogEntry) -> str:
    role = entry.role if getattr(entry, "role", None) else "NARRATION"
    content = (entry.content or "").strip()
    return f"[{role}] {content}"


def _format_growth_rewards(growth_rewards: list[GrowthReward]) -> str:
    if not growth_rewards:
        return "없음"

    lines = []
    for reward in growth_rewards:
        lines.append(
            f"- {reward.character_name} ({reward.growth_type}): "
            f"{reward.growth_detail} / 이유: {reward.narrative_reason}"
        )
    return "\n".join(lines)


async def generate_updated_ai_summary(
    previous_summary: str | None,
    completed_act: StoryActInfo,
    act_story_entries: list[StoryLogEntry],
    growth_rewards: list[GrowthReward],
    llm_model: str = "gpt-4o",
) -> str:
    """Act 종료 시점에 누적 요약을 갱신합니다."""
    logger.info(
        "Generating updated ai_summary for completed act: "
        f"{completed_act.act_number}막 ({completed_act.title})"
    )

    # Act 내 로그는 순서가 중요하므로 시간순으로 유지
    sorted_entries = sorted(
        act_story_entries,
        key=lambda e: (getattr(e, "created_at", None) is None, getattr(e, "created_at", None)),
    )

    # Act 로그가 과도하게 길어지면 앞/뒤를 샘플링해 토큰 폭주를 방지한다.
    if len(sorted_entries) > 120:
        head = sorted_entries[:40]
        tail = sorted_entries[-80:]
        omitted_count = len(sorted_entries) - (len(head) + len(tail))
        story_text = (
            "\n".join(_format_story_entry(entry) for entry in head)
            + f"\n... 중간 로그 {omitted_count}개 생략 ...\n"
            + "\n".join(_format_story_entry(entry) for entry in tail)
        )
    else:
        story_text = "\n".join(_format_story_entry(entry) for entry in sorted_entries)

    context = (
        "## 기존 누적 요약\n"
        f"{(previous_summary or '없음').strip() or '없음'}\n\n"
        "## 이번에 종료된 막\n"
        f"- 막 번호: {completed_act.act_number}\n"
        f"- 제목: {completed_act.title}\n"
        f"- 부제: {completed_act.subtitle or '없음'}\n\n"
        "## 이번 막의 스토리 로그 (시간순)\n"
        f"{story_text or '없음'}\n\n"
        "## 이번 막 종료 보상\n"
        f"{_format_growth_rewards(growth_rewards)}\n"
    )

    system_instruction = (
        "너는 TRPG 장기 메모리 편집기다.\n"
        "목표는 다음 막에서 세계 상태가 끊기지 않도록 사실 기반 누적 요약을 만드는 것이다.\n"
        "출력 규칙:\n"
        "1) 한국어 평문으로만 작성\n"
        "2) 700~1400자\n"
        "3) 사실만 기록 (추측 금지)\n"
        "4) 적/중요 NPC의 생사와 상태, 진행중인 갈등, 해결/미해결 사건을 명시\n"
        "5) 기존 누적 요약의 유효 정보는 유지하고, 이번 막 변화로 갱신\n"
        "6) 다음 막 시작 시 즉시 참조 가능한 형태로 간결하게 작성\n"
    )

    chat_template = ChatPromptTemplate.from_messages(
        [
            ("system", system_instruction),
            ("human", "{context}\n\n위 정보를 기반으로 '업데이트된 누적 요약'을 작성하세요."),
        ]
    )

    llm = ChatLiteLLM(
        model=llm_model,
        temperature=0.2,
        max_tokens=2000,
    )

    chain = chat_template | llm
    response = await chain.ainvoke({"context": context})
    summary = (response.content or "").strip()

    if not summary:
        raise ValueError("생성된 요약이 비어있습니다")

    logger.info(f"Updated ai_summary generated: {len(summary)} chars")
    return summary
