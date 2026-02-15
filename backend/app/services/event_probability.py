"""
점진적 랜덤 이벤트 확률 시스템.

서버 사이드 주사위 굴림으로 AI가 새로운 돌발 사건을 도입할지 결정합니다.
확률은 매 턴 증가하고, 이벤트 발동 시 초기값으로 리셋됩니다.
"""

import logging
import random

from sqlalchemy.orm import Session as DBSession

from app.models import GameSession

logger = logging.getLogger("ai_gm.event_probability")

# ──────────────────────────────────────────────
# 조정 가능한 상수 (테스트하며 값을 바꿔보세요)
# ──────────────────────────────────────────────
BASE_EVENT_PROBABILITY: float = 0.00  # 시작/리셋 확률 0%
EVENT_PROBABILITY_INCREMENT: float = 0.02  # 매 턴 +2%
MAX_EVENT_PROBABILITY: float = 0.70  # 안전 상한 70%


def roll_event_trigger(session_id: int, db: DBSession) -> bool:
    """현재 확률로 이벤트 발동 여부를 판정합니다.

    Args:
        session_id: 게임 세션 ID
        db: DB 세션

    Returns:
        True면 이번 턴에 돌발 이벤트 발생
    """
    session = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not session:
        logger.warning(f"Session {session_id} not found for event roll")
        return False

    current_prob = session.event_probability if session.event_probability is not None else BASE_EVENT_PROBABILITY
    roll = random.random()
    triggered = roll < current_prob

    logger.info(
        f"Event roll: session={session_id}, "
        f"probability={current_prob:.0%}, roll={roll:.4f}, triggered={triggered}"
    )

    return triggered


def update_event_probability(session_id: int, db: DBSession, event_fired: bool) -> float:
    """이벤트 발동 여부에 따라 확률을 갱신합니다.

    발동 시: BASE로 리셋
    미발동 시: INCREMENT만큼 증가 (MAX 이하)

    Args:
        session_id: 게임 세션 ID
        db: DB 세션
        event_fired: 이번 턴에 이벤트가 발동했는지

    Returns:
        갱신된 확률 값
    """
    session = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not session:
        logger.warning(f"Session {session_id} not found for probability update")
        return BASE_EVENT_PROBABILITY

    if event_fired:
        new_prob = BASE_EVENT_PROBABILITY
    else:
        current = session.event_probability if session.event_probability is not None else BASE_EVENT_PROBABILITY
        new_prob = min(current + EVENT_PROBABILITY_INCREMENT, MAX_EVENT_PROBABILITY)

    session.event_probability = new_prob
    db.commit()

    logger.info(
        f"Event probability updated: session={session_id}, "
        f"event_fired={event_fired}, new={new_prob:.0%}"
    )

    return new_prob


def build_event_context_instruction(event_triggered: bool) -> str:
    """프롬프트 컨텍스트에 주입할 이벤트 지시문을 생성합니다."""
    if event_triggered:
        return (
            "## 랜덤 이벤트 발생 지시\n\n"
            "이번 서술에서는 **새로운 돌발 사건**을 자연스럽게 도입하세요.\n"
            "현재 진행 중인 상황의 흐름 속에서 개연성 있게 등장해야 합니다.\n"
            "예시: 예기치 못한 제3세력의 등장, 환경의 급격한 변화, 숨겨진 함정의 발동, "
            "NPC의 돌발 행동, 새로운 위협이나 기회의 출현 등.\n"
            "사건은 세계관에 부합하고, 현재 장면의 톤을 존중하면서도 "
            "이야기에 새로운 긴장감과 전환점을 부여해야 합니다.\n"
            "기존 '떡밥 투하 규칙'에 더하여, 이 돌발 사건이 서술의 핵심 전개 중 하나가 되도록 하세요."
        )
    else:
        return (
            "## 스토리 집중 지시\n\n"
            "이번 서술에서는 **현재 진행 중인 사건과 상황에 집중**하세요.\n"
            "새로운 돌발 사건을 인위적으로 만들지 말고, "
            "플레이어들의 행동 결과와 기존 스토리 흐름을 자연스럽게 이어가세요.\n"
            "기존 '떡밥 투하 규칙'에 따라 서술 마무리에 다음 행동 유발 요소를 포함하되, "
            "이는 현재 상황의 자연스러운 연장선이어야 합니다."
        )
