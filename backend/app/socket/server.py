"""소켓 서버 코어 모듈.

Socket.io 서버 인스턴스와 로거를 관리합니다.
"""

import logging

import socketio

# Socket.io 서버 인스턴스 (ASGI 모드)
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True,
)

# AI GM 관련 이벤트 로거
logger = logging.getLogger("ai_gm.socket")
