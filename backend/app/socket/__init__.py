"""소켓 서버 패키지.

실시간 통신을 위한 Socket.io 서버 모듈을 제공합니다.
이 패키지는 다음 하위 모듈로 구성됩니다:

- server: Socket.io 서버 인스턴스 및 전역 상태
- managers: 비즈니스 로직 (참가자, 세션, 액션큐, presence 관리)
- handlers: 소켓 이벤트 핸들러
- utils: 유틸리티 함수
"""

from app.socket.server import logger, sio

# 모든 핸들러 등록
from app.socket.handlers import register_all_handlers

register_all_handlers(sio)

__all__ = ["sio", "logger"]
