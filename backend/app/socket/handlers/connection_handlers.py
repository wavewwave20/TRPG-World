"""연결 관련 이벤트 핸들러 모듈.

클라이언트 연결, 해제, 채팅 메시지 이벤트를 처리합니다.
"""

from app.database import SessionLocal
from app.models import Character, GameSession, SessionParticipant
from app.socket.managers.participant_manager import (
    get_participants,
    remove_participant,
)
from app.socket.managers.presence_manager import (
    remove_presence,
    start_presence_monitor,
)
from app.socket.managers.session_manager import (
    check_and_deactivate_session,
    maybe_end_session_if_host,
)
from app.socket.server import logger
from app.socket.utils.validators import validate_chat_message


def register_handlers(sio):
    """연결 관련 이벤트 핸들러를 등록합니다.

    인자:
        sio: Socket.io 서버 인스턴스
    """

    @sio.event
    async def connect(sid, environ):
        """클라이언트 연결을 처리합니다.

        최초 연결 시 presence 모니터 태스크를 시작합니다.

        인자:
            sid: 소켓 세션 ID (이 연결의 고유 식별자)
            environ: ASGI 환경 딕셔너리
        """
        logger.info(f"클라이언트 연결: {sid}")

        # 최초 연결 시 presence 모니터 시작
        await start_presence_monitor(sio)

    @sio.event
    async def disconnect(sid):
        """클라이언트 연결 해제를 처리합니다.

        연결 해제 시:
        1. presence 추적 정리
        2. SessionParticipant 레코드 제거
        3. user_left 이벤트 브로드캐스트
        4. 호스트였다면 세션 종료
        5. 세션 비활성화 확인

        인자:
            sid: 소켓 세션 ID
        """
        logger.info(f"클라이언트 연결 해제: {sid}")

        # presence 추적 정리
        info = remove_presence(sid)

        if info and info.get("session_id") and info.get("user_id"):
            session_id = info["session_id"]
            user_id = info["user_id"]

            db = SessionLocal()
            try:
                # 참가자 제거 전 캐릭터 이름 조회
                char_row = (
                    db.query(Character.name)
                    .join(
                        SessionParticipant,
                        SessionParticipant.character_id == Character.id,
                    )
                    .filter(
                        SessionParticipant.session_id == session_id,
                        SessionParticipant.user_id == user_id,
                    )
                    .first()
                )
                character_name = char_row[0] if char_row else None

                # SessionParticipant 제거
                removed = remove_participant(db, session_id, user_id)

                if removed:
                    # 업데이트된 참가자 목록 조회
                    participants = get_participants(db, session_id)

                    # user_left 이벤트 브로드캐스트
                    room_name = f"session_{session_id}"
                    await sio.emit(
                        "user_left",
                        {
                            "user_id": user_id,
                            "session_id": session_id,
                            "character_name": character_name,
                            "participants": participants,
                            "participant_count": len(participants),
                        },
                        room=room_name,
                    )

                    logger.info(f"클라이언트 {sid} 세션 {session_id}에서 연결 해제, 참가자 제거됨")

                # 호스트였다면 세션 종료
                await maybe_end_session_if_host(session_id, user_id, sio)

                # 세션 비활성화 확인
                await check_and_deactivate_session(session_id, db, sio)

            except Exception as e:
                print(f"연결 해제 정리 중 에러 ({sid}): {e}")
                db.rollback()
            finally:
                db.close()

    @sio.event
    async def chat_message(sid, data):
        """채팅 메시지를 처리합니다.

        일시적인 채팅 메시지를 세션 내 모든 참가자에게 브로드캐스트합니다.
        메시지는 데이터베이스에 저장되지 않습니다.

        인자:
            sid: 소켓 세션 ID
            data: 메시지 데이터
                - session_id: 게임 세션 ID
                - user_id: 사용자 ID
                - message: 메시지 텍스트
        """
        try:
            session_id = data.get("session_id")
            user_id = data.get("user_id")
            message = data.get("message") or ""

            if not session_id:
                await sio.emit("error", {"message": "session_id가 필요합니다"}, room=sid)
                return

            # 캐릭터 이름 조회
            db = SessionLocal()
            try:
                row = (
                    db.query(Character.name)
                    .join(
                        SessionParticipant,
                        SessionParticipant.character_id == Character.id,
                    )
                    .filter(
                        SessionParticipant.session_id == session_id,
                        SessionParticipant.user_id == user_id,
                    )
                    .first()
                )
                username = row[0] if row else (f"User {user_id}" if user_id else "User")
            finally:
                db.close()

            # 메시지 유효성 검사
            is_valid, error_message = validate_chat_message(message)
            if not is_valid:
                await sio.emit("error", {"message": error_message}, room=sid)
                return

            # 세션 존재 확인
            db = SessionLocal()
            try:
                session = db.query(GameSession).filter(GameSession.id == session_id).first()
                if not session:
                    await sio.emit("error", {"message": "세션을 찾을 수 없습니다"}, room=sid)
                    return
            finally:
                db.close()

            # 채팅 메시지 브로드캐스트 (일시적)
            room_name = f"session_{session_id}"
            await sio.emit(
                "chat_message",
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "character_name": username,
                    "message": message.strip(),
                },
                room=room_name,
            )

        except Exception as e:
            print(f"chat_message 에러: {e}")
            await sio.emit("error", {"message": "채팅 메시지 전송 실패"}, room=sid)
