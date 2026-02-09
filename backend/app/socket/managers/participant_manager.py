"""참가자 관리 모듈.

세션 참가자의 추가, 제거, 조회 기능을 제공합니다.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Character, SessionParticipant


def add_participant(db: Session, session_id: int, user_id: int, character_id: int) -> SessionParticipant:
    """참가자를 추가하거나 업데이트합니다.

    이미 존재하는 참가자인 경우 캐릭터 ID와 참가 시간을 업데이트합니다.
    새로운 참가자인 경우 새 레코드를 생성합니다.

    인자:
        db: 데이터베이스 세션
        session_id: 게임 세션 ID
        user_id: 사용자 ID
        character_id: 캐릭터 ID

    반환값:
        SessionParticipant: 생성되거나 업데이트된 참가자 레코드

    예외:
        Exception: 데이터베이스 작업 실패 시 (호출자가 롤백 처리해야 함)
    """
    # 기존 참가자 확인
    existing = (
        db.query(SessionParticipant)
        .filter(
            SessionParticipant.session_id == session_id,
            SessionParticipant.user_id == user_id,
        )
        .first()
    )

    if existing:
        # 캐릭터 ID와 참가 시간 업데이트
        existing.character_id = character_id
        existing.joined_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    # 새 참가자 생성
    participant = SessionParticipant(
        session_id=session_id,
        user_id=user_id,
        character_id=character_id,
        joined_at=datetime.utcnow(),
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant


def remove_participant(db: Session, session_id: int, user_id: int) -> bool:
    """참가자를 제거합니다.

    인자:
        db: 데이터베이스 세션
        session_id: 게임 세션 ID
        user_id: 사용자 ID

    반환값:
        bool: 레코드가 제거되었으면 True, 아니면 False

    예외:
        Exception: 데이터베이스 작업 실패 시 (호출자가 롤백 처리해야 함)
    """
    participant = (
        db.query(SessionParticipant)
        .filter(
            SessionParticipant.session_id == session_id,
            SessionParticipant.user_id == user_id,
        )
        .first()
    )

    if participant:
        db.delete(participant)
        db.commit()
        return True

    return False


def get_participant_count(db: Session, session_id: int) -> int:
    """세션의 참가자 수를 반환합니다.

    인자:
        db: 데이터베이스 세션
        session_id: 게임 세션 ID

    반환값:
        int: 세션의 참가자 수
    """
    return db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id).count()


def get_participants(db: Session, session_id: int) -> list[dict]:
    """세션의 모든 참가자 정보를 반환합니다.

    캐릭터 정보와 함께 참가자 목록을 조회합니다.

    인자:
        db: 데이터베이스 세션
        session_id: 게임 세션 ID

    반환값:
        list[dict]: 참가자 정보 딕셔너리 목록
            - user_id: 사용자 ID
            - character_id: 캐릭터 ID
            - character_name: 캐릭터 이름
    """
    results = (
        db.query(
            SessionParticipant.user_id,
            SessionParticipant.character_id,
            Character.name.label("character_name"),
        )
        .join(Character, Character.id == SessionParticipant.character_id)
        .filter(SessionParticipant.session_id == session_id)
        .all()
    )

    return [
        {
            "user_id": r.user_id,
            "character_id": r.character_id,
            "character_name": r.character_name,
        }
        for r in results
    ]


def remove_participant_db(session_id: int | None, user_id: int | None) -> None:
    """데이터베이스에서 참가자를 제거합니다 (최선의 노력).

    별도의 데이터베이스 세션을 생성하여 참가자를 제거합니다.
    실패해도 예외를 발생시키지 않습니다.

    인자:
        session_id: 게임 세션 ID (None이면 무시)
        user_id: 사용자 ID (None이면 무시)
    """
    if not session_id or not user_id:
        return

    db = SessionLocal()
    try:
        participant = (
            db.query(SessionParticipant)
            .filter(
                SessionParticipant.session_id == session_id,
                SessionParticipant.user_id == user_id,
            )
            .first()
        )
        if participant:
            db.delete(participant)
            db.commit()
    except Exception as e:
        print(f"참가자 DB 제거 실패 (session={session_id}, user={user_id}): {e}")
    finally:
        db.close()
