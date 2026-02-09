"""이벤트 핸들러 패키지.

Socket.io 이벤트 핸들러 모듈들을 제공합니다.

- connection_handlers: 연결/해제/채팅 이벤트
- session_handlers: 세션 참가/퇴장 이벤트
- action_handlers: 액션 큐 관련 이벤트
- ai_gm_handlers: AI GM 판정 및 이야기 생성 이벤트
- heartbeat_handlers: 하트비트 이벤트
"""

from app.socket.handlers.action_handlers import (
    register_handlers as register_action_handlers,
)
from app.socket.handlers.ai_gm_handlers import (
    register_handlers as register_ai_gm_handlers,
)
from app.socket.handlers.connection_handlers import (
    register_handlers as register_connection_handlers,
)
from app.socket.handlers.heartbeat_handlers import (
    register_handlers as register_heartbeat_handlers,
)
from app.socket.handlers.session_handlers import (
    register_handlers as register_session_handlers,
)


def register_all_handlers(sio):
    """모든 이벤트 핸들러를 등록합니다.

    인자:
        sio: Socket.io 서버 인스턴스
    """
    register_connection_handlers(sio)
    register_session_handlers(sio)
    register_action_handlers(sio)
    register_ai_gm_handlers(sio)
    register_heartbeat_handlers(sio)


__all__ = ["register_all_handlers"]
