"""Presence 관리 모듈.

클라이언트 연결 상태와 하트비트를 관리합니다.
하트비트 타임아웃 시 클라이언트를 세션에서 제거합니다.
"""

import asyncio
import time

from app.database import SessionLocal
from app.models import Character, SessionParticipant
from app.socket.server import logger

# Presence 추적
# 구조: {sid: {'session_id': int, 'user_id': int, 'last_ts': float}}
session_presence: dict[str, dict] = {}

# 하트비트 설정
HEARTBEAT_INTERVAL_SEC = 5
# 1회 누락 허용 => 2회 누락 후 연결 해제
HEARTBEAT_TIMEOUT_SEC = HEARTBEAT_INTERVAL_SEC * 2 + 0.5  # 약간의 버퍼

# 백그라운드 태스크 상태
_presence_task_started = False


def update_presence(sid: str, session_id: int, user_id: int) -> None:
    """클라이언트의 presence를 업데이트합니다.

    하트비트 수신 시 호출하여 마지막 활동 시간을 갱신합니다.

    인자:
        sid: 소켓 세션 ID
        session_id: 게임 세션 ID
        user_id: 사용자 ID
    """
    session_presence[sid] = {
        "session_id": session_id,
        "user_id": user_id,
        "last_ts": time.monotonic(),
    }


def remove_presence(sid: str) -> dict | None:
    """클라이언트의 presence를 제거하고 정보를 반환합니다.

    인자:
        sid: 소켓 세션 ID

    반환값:
        dict | None: 제거된 presence 정보, 없으면 None
    """
    return session_presence.pop(sid, None)


def get_presence(sid: str) -> dict | None:
    """클라이언트의 presence 정보를 반환합니다.

    인자:
        sid: 소켓 세션 ID

    반환값:
        dict | None: presence 정보, 없으면 None
    """
    return session_presence.get(sid)


def clear_session_presence(session_id: int) -> None:
    """세션의 모든 presence를 제거합니다.

    세션 종료 시 해당 세션의 모든 클라이언트 presence를 정리합니다.

    인자:
        session_id: 게임 세션 ID
    """
    for sid, info in list(session_presence.items()):
        if info.get("session_id") == session_id:
            session_presence.pop(sid, None)


def find_sid_by_user(session_id: int, user_id: int) -> str | None:
    """세션 내 사용자의 소켓 ID를 찾습니다.

    인자:
        session_id: 게임 세션 ID
        user_id: 사용자 ID

    반환값:
        str | None: 소켓 세션 ID, 없으면 None
    """
    for sid, info in session_presence.items():
        if info.get("session_id") == session_id and info.get("user_id") == user_id:
            return sid
    return None


async def start_presence_monitor(sio) -> None:
    """Presence 모니터 태스크를 시작합니다.

    최초 연결 시 한 번만 호출되어 백그라운드 태스크를 시작합니다.

    인자:
        sio: Socket.io 서버 인스턴스
    """
    global _presence_task_started

    if _presence_task_started:
        return

    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_presence_monitor_loop(sio))
        _presence_task_started = True
    except Exception as e:
        print(f"Presence 모니터 시작 실패: {e}")


async def _presence_monitor_loop(sio) -> None:
    """하트비트 타임아웃을 주기적으로 확인합니다.

    타임아웃된 클라이언트를 세션에서 제거하고 관련 이벤트를 발생시킵니다.

    인자:
        sio: Socket.io 서버 인스턴스
    """
    # 순환 import 방지를 위해 지연 import
    from app.socket.managers.participant_manager import (
        get_participants,
        remove_participant,
    )
    from app.socket.managers.session_manager import (
        check_and_deactivate_session,
        maybe_end_session_if_host,
    )

    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SEC)
        now = time.monotonic()

        # 스냅샷으로 순회 (루프 중 수정 허용)
        for sid, info in list(session_presence.items()):
            last_ts = info.get("last_ts", 0)
            session_id = info.get("session_id")
            user_id = info.get("user_id")

            if not session_id or not user_id:
                continue

            # 하트비트 타임아웃 확인
            if now - last_ts > HEARTBEAT_TIMEOUT_SEC:
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

                    # 참가자 DB에서 제거
                    remove_participant(db, session_id, user_id)

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

                    # 소켓 룸에서 제거
                    await sio.leave_room(sid, room_name)

                    # presence 레코드 제거
                    session_presence.pop(sid, None)

                    print(f"클라이언트 {sid} 타임아웃: 세션 {session_id}")

                    # 호스트였다면 세션 즉시 종료
                    await maybe_end_session_if_host(session_id, user_id, sio)

                    # 세션 비활성화 확인
                    await check_and_deactivate_session(session_id, db, sio)

                except Exception as e:
                    logger.error(f"presence 타임아웃 처리 에러: {sid}, {e}")
                    db.rollback()
                finally:
                    db.close()
