"""매니저 모듈 패키지.

비즈니스 로직을 담당하는 매니저 모듈들을 제공합니다.

- participant_manager: 세션 참가자 관리
- session_manager: 게임 세션 생명주기 관리
- action_queue_manager: 플레이어 액션 큐 관리
- presence_manager: 클라이언트 연결 상태 관리
"""

from app.socket.managers.action_queue_manager import (
    add_action,
    clear_queue,
    delete_action,
    edit_action,
    get_queue,
    reorder_actions,
)
from app.socket.managers.participant_manager import (
    add_participant,
    get_participant_count,
    get_participants,
    remove_participant,
    remove_participant_db,
)
from app.socket.managers.presence_manager import (
    clear_session_presence,
    find_sid_by_user,
    get_presence,
    remove_presence,
    session_presence,
    start_presence_monitor,
    update_presence,
)
from app.socket.managers.session_manager import (
    check_and_deactivate_session,
    maybe_end_session_if_host,
    verify_host_authorization,
)

__all__ = [
    # participant_manager
    "add_participant",
    "remove_participant",
    "get_participant_count",
    "get_participants",
    "remove_participant_db",
    # session_manager
    "check_and_deactivate_session",
    "verify_host_authorization",
    "maybe_end_session_if_host",
    # action_queue_manager
    "add_action",
    "edit_action",
    "delete_action",
    "reorder_actions",
    "get_queue",
    "clear_queue",
    # presence_manager
    "session_presence",
    "update_presence",
    "remove_presence",
    "get_presence",
    "clear_session_presence",
    "find_sid_by_user",
    "start_presence_monitor",
]
