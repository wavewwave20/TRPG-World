"""세션 관리 모듈.

게임 세션의 생명주기와 권한 검증을 담당합니다.
"""

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import GameSession, SessionParticipant
from app.socket.managers.participant_manager import get_participant_count
from app.socket.server import logger
from app.utils.backups import backup_session


async def check_and_deactivate_session(session_id: int, db: Session, sio=None) -> bool:
    """세션 비활성화 조건을 확인하고 필요시 비활성화합니다.

    참가자 수가 0이 되면 세션을 비활성화합니다.
    비활성화 시:
    1. is_active를 False로 설정
    2. 스토리 로그 백업
    3. 모든 SessionParticipant 레코드 제거
    4. session_ended 이벤트 브로드캐스트
    5. 소켓 룸 닫기
    6. presence 항목 정리

    인자:
        session_id: 게임 세션 ID
        db: 데이터베이스 세션
        sio: Socket.io 서버 인스턴스 (이벤트 전송용)

    반환값:
        bool: 세션이 비활성화되었으면 True, 아니면 False
    """
    # 순환 import 방지를 위해 지연 import
    from app.socket.managers.presence_manager import (
        clear_session_presence,
    )

    if sio is None:
        from app.socket.server import sio as default_sio

        sio = default_sio

    try:
        # 참가자 수 확인
        count = get_participant_count(db, session_id)

        if count > 0:
            return False

        # 세션 조회
        session = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not session or not session.is_active:
            return False

        # is_active를 False로 설정
        session.is_active = False

        # 스토리 로그 백업
        try:
            backup_session(session_id)
        except Exception as e:
            print(f"세션 {session_id} 백업 실패: {e}")

        # 남은 참가자 레코드 제거 (0이어야 하지만 안전하게)
        db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id).delete()

        db.commit()

        # session_ended 이벤트 브로드캐스트
        room_name = f"session_{session_id}"
        await sio.emit(
            "session_ended",
            {"session_id": session_id, "reason": "no_participants"},
            room=room_name,
        )

        # 소켓 룸 닫기
        try:
            await sio.close_room(room_name)
        except Exception as e:
            print(f"룸 {room_name} 닫기 실패: {e}")

        # presence 항목 정리
        clear_session_presence(session_id)

        logger.info(f"세션 {session_id} 비활성화: 참가자 없음")
        return True

    except Exception as e:
        logger.error(f"check_and_deactivate_session 에러: {e}")
        db.rollback()
        return False


async def verify_host_authorization(session_id: int, user_id: int, db: Session) -> tuple[bool, str | None]:
    """사용자가 세션의 호스트인지 확인합니다.

    인자:
        session_id: 게임 세션 ID
        user_id: 확인할 사용자 ID
        db: 데이터베이스 세션

    반환값:
        (권한 여부, 오류 메시지) 튜플
        - 권한 있음: (True, None)
        - 권한 없음: (False, 오류 메시지)
    """
    try:
        session = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not session:
            return False, "세션을 찾을 수 없습니다"

        if session.host_user_id != user_id:
            return False, "권한 없음: 호스트만 이 작업을 수행할 수 있습니다"

        return True, None
    except Exception as e:
        logger.error(f"verify_host_authorization 에러: {e}")
        return False, "내부 서버 오류"


async def maybe_end_session_if_host(session_id: int | None, user_id: int | None, sio=None) -> None:
    """호스트 연결 해제 시 세션을 즉시 종료합니다.

    호스트가 연결을 끊으면 남은 참가자 수와 관계없이 세션을 즉시 비활성화합니다.
    이를 통해 호스트 없이 세션이 계속되는 것을 방지합니다.

    인자:
        session_id: 게임 세션 ID (None이면 무시)
        user_id: 연결 해제된 사용자 ID (None이면 무시)
        sio: Socket.io 서버 인스턴스 (이벤트 전송용)
    """
    # 순환 import 방지를 위해 지연 import
    from app.socket.managers.presence_manager import clear_session_presence

    if not session_id or not user_id:
        return

    if sio is None:
        from app.socket.server import sio as default_sio

        sio = default_sio

    db = SessionLocal()
    try:
        session = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not session:
            return

        # 연결 해제된 사용자가 호스트인 경우에만 진행
        if session.host_user_id != user_id:
            return

        # 세션 즉시 비활성화
        session.is_active = False

        # 스토리 로그 백업
        try:
            backup_session(session_id)
        except Exception as e:
            print(f"세션 {session_id} 백업 실패: {e}")

        # 모든 참가자 레코드 제거
        db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id).delete()

        db.commit()

        logger.info(f"세션 {session_id} 종료: 호스트 연결 해제 (user_id={user_id})")

    except Exception as e:
        print(f"maybe_end_session_if_host 에러: {e}")
        db.rollback()
    finally:
        db.close()

    room_name = f"session_{session_id}"

    # session_ended 이벤트 브로드캐스트 (reason: host_disconnected)
    await sio.emit(
        "session_ended",
        {"session_id": session_id, "reason": "host_disconnected"},
        room=room_name,
    )

    # 소켓 룸 닫기
    try:
        await sio.close_room(room_name)
    except Exception as e:
        print(f"룸 {room_name} 닫기 실패: {e}")

    # presence 항목 정리
    clear_session_presence(session_id)
