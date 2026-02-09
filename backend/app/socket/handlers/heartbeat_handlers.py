"""하트비트 관련 이벤트 핸들러 모듈.

클라이언트 하트비트 이벤트를 처리합니다.
"""

from app.socket.managers.presence_manager import update_presence
from app.socket.server import logger


def register_handlers(sio):
    """하트비트 관련 이벤트 핸들러를 등록합니다.

    인자:
        sio: Socket.io 서버 인스턴스
    """

    @sio.event
    async def session_heartbeat(sid, data):
        """클라이언트로부터 주기적인 하트비트를 수신합니다.

        클라이언트가 세션 페이지에 있는 동안 주기적으로 전송됩니다.
        하트비트를 수신하면 해당 클라이언트의 presence를 업데이트합니다.

        인자:
            sid: 소켓 세션 ID
            data: 하트비트 데이터
                - session_id: 게임 세션 ID
                - user_id: 사용자 ID
        """
        try:
            session_id = data.get("session_id")
            user_id = data.get("user_id")

            if not session_id or not user_id:
                # 잘못된 형식의 하트비트는 무시
                return

            # 해당 sid의 presence 업데이트
            update_presence(sid, session_id, user_id)

        except Exception as e:
            logger.error(f"session_heartbeat 에러: {e}")
