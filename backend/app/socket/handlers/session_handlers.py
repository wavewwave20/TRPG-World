"""세션 관련 이벤트 핸들러 모듈.

세션 참가, 퇴장 이벤트를 처리합니다.
"""


from app.database import SessionLocal
from app.models import Character, GameSession, SessionParticipant
from app.services.session_activity_logger import log_session_activity
from app.socket.managers.participant_manager import (
    add_participant,
    get_participants,
    remove_participant,
)
from app.socket.managers.presence_manager import remove_presence, update_presence
from app.socket.managers.session_manager import (
    cancel_host_grace_timer,
    check_and_deactivate_session,
)
from app.socket.server import logger


def register_handlers(sio):
    """세션 관련 이벤트 핸들러를 등록합니다.

    인자:
        sio: Socket.io 서버 인스턴스
    """

    @sio.event
    async def join_session(sid, data):
        """세션 참가 요청을 처리합니다.

        참가 시:
        1. 세션 존재 및 활성 상태 확인
        2. SessionParticipant 레코드 추가
        3. 소켓 룸에 참가
        4. presence 초기화
        5. user_joined 이벤트 브로드캐스트

        인자:
            sid: 소켓 세션 ID
            data: 참가 데이터
                - session_id: 게임 세션 ID
                - user_id: 사용자 ID
                - character_id: 캐릭터 ID
        """
        try:
            session_id = data.get("session_id")
            user_id = data.get("user_id")
            character_id = data.get("character_id")

            # 필수 필드 확인
            if not session_id or not user_id or not character_id:
                await sio.emit(
                    "error",
                    {"message": "session_id, user_id, character_id가 필요합니다"},
                    room=sid,
                )
                return

            db = SessionLocal()
            try:
                # 세션 존재 및 활성 상태 확인
                session = db.query(GameSession).filter(GameSession.id == session_id).first()
                if not session:
                    await sio.emit("error", {"message": "세션을 찾을 수 없습니다."}, room=sid)
                    return

                # 비활성 세션 거부
                if not session.is_active:
                    await sio.emit("error", {"message": "세션이 종료되었습니다."}, room=sid)
                    return

                # 호스트 재연결 시 그레이스 타이머 취소
                if session.host_user_id == user_id:
                    cancel_host_grace_timer(session_id)

                existing_participant = (
                    db.query(SessionParticipant)
                    .filter(
                        SessionParticipant.session_id == session_id,
                        SessionParticipant.user_id == user_id,
                    )
                    .first()
                )
                reconnected = existing_participant is not None

                # 참가자 추가 (SessionParticipant 레코드 생성/업데이트)
                add_participant(db, session_id, user_id, character_id)

                # 캐릭터 이름 조회
                character = db.query(Character).filter(Character.id == character_id).first()
                character_name = character.name if character else None

                # 소켓 룸에 참가
                room_name = f"session_{session_id}"
                await sio.enter_room(sid, room_name)

                # presence 초기화 (하트비트로 업데이트됨)
                update_presence(sid, session_id, user_id)

                # 업데이트된 참가자 목록 조회
                participants = get_participants(db, session_id)
                log_session_activity(
                    db,
                    session_id=session_id,
                    actor_user_id=user_id,
                    actor_character_id=character_id,
                    source="socket",
                    action_type="session.socket_rejoin" if reconnected else "session.socket_join",
                    status="success",
                    message="소켓 세션 재참가" if reconnected else "소켓 세션 참가",
                    detail={
                        "participant_count": len(participants),
                        "reconnected": reconnected,
                    },
                )
                db.commit()

                # user_joined 이벤트 브로드캐스트
                await sio.emit(
                    "user_joined",
                    {
                        "user_id": user_id,
                        "session_id": session_id,
                        "character_name": character_name,
                        "participants": participants,
                        "participant_count": len(participants),
                        "reconnected": reconnected,
                    },
                    room=room_name,
                )

                await sio.emit(
                    "session_participant_count_updated",
                    {
                        "session_id": session_id,
                        "participant_count": len(participants),
                        "is_active": True,
                    },
                )

                logger.info(f"클라이언트 {sid} 세션 {session_id} 참가: 캐릭터={character_name}")

            finally:
                db.close()

        except Exception as e:
            print(f"join_session 에러: {e}")
            await sio.emit("error", {"message": "세션 참가 실패"}, room=sid)

    @sio.event
    async def leave_session(sid, data):
        """세션 퇴장 요청을 처리합니다.

        퇴장 시:
        1. SessionParticipant 레코드 제거
        2. 소켓 룸에서 퇴장
        3. presence 정리
        4. user_left 이벤트 브로드캐스트
        5. 세션 비활성화 확인

        인자:
            sid: 소켓 세션 ID
            data: 퇴장 데이터
                - session_id: 게임 세션 ID
                - user_id: 사용자 ID
        """
        try:
            session_id = data.get("session_id")
            user_id = data.get("user_id")

            if not session_id or not user_id:
                await sio.emit("error", {"message": "session_id와 user_id가 필요합니다"}, room=sid)
                return

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

                # 참가자 제거
                remove_participant(db, session_id, user_id)

                # 소켓 룸에서 퇴장
                room_name = f"session_{session_id}"
                await sio.leave_room(sid, room_name)

                # presence 정리
                remove_presence(sid)

                # 업데이트된 참가자 목록 조회
                participants = get_participants(db, session_id)
                log_session_activity(
                    db,
                    session_id=session_id,
                    actor_user_id=user_id,
                    source="socket",
                    action_type="session.socket_leave",
                    status="success",
                    message="소켓 세션 퇴장",
                    detail={"participant_count": len(participants)},
                )
                db.commit()

                # user_left 이벤트 브로드캐스트
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

                logger.info(f"클라이언트 {sid} 세션 {session_id} 퇴장")

                # 세션 비활성화 확인
                await check_and_deactivate_session(session_id, db, sio)

                refreshed = db.query(GameSession).filter(GameSession.id == session_id).first()
                await sio.emit(
                    "session_participant_count_updated",
                    {
                        "session_id": session_id,
                        "participant_count": len(participants),
                        "is_active": bool(refreshed and refreshed.is_active),
                    },
                )

            finally:
                db.close()

        except Exception as e:
            print(f"leave_session 에러: {e}")
            await sio.emit("error", {"message": "세션 퇴장 실패"}, room=sid)
