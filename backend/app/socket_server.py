"""실시간 통신을 위한 Socket.io 서버.

이 파일은 하위 호환성을 위한 래퍼입니다.
실제 구현은 app.socket 패키지에 있습니다.

사용 예:
    from app.socket_server import sio
    # 또는
    from app.socket import sio
"""

# 새 모듈에서 re-export
from app.socket import logger, sio

# 하위 호환성을 위해 매니저 함수들도 노출
from app.socket.managers import (
    add_participant,
    check_and_deactivate_session,
    get_participant_count,
    get_participants,
    maybe_end_session_if_host,
    remove_participant,
    session_presence,
    verify_host_authorization,
)

# 액션 큐 관련 (기존 코드에서 직접 접근하는 경우를 위해)
from app.socket.managers.action_queue_manager import action_queues

__all__ = [
    "sio",
    "logger",
    # 참가자 관리
    "add_participant",
    "remove_participant",
    "get_participant_count",
    "get_participants",
    # 세션 관리
    "check_and_deactivate_session",
    "verify_host_authorization",
    "maybe_end_session_if_host",
    # Presence
    "session_presence",
    # 액션 큐
    "action_queues",
]
