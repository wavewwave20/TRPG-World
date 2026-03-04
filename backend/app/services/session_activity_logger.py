"""세션 활동 로그 저장 유틸."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import SessionActivityLog

_VALID_STATUSES = {"info", "started", "success", "failed", "skipped"}


def log_session_activity(
    db: Session,
    *,
    session_id: int,
    action_type: str,
    status: str = "info",
    source: str = "system",
    message: str | None = None,
    actor_user_id: int | None = None,
    actor_character_id: int | None = None,
    detail: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> SessionActivityLog:
    """세션 활동 로그를 추가합니다.

    dedupe_key가 주어지면 같은 세션에 동일 키가 이미 있는 경우
    기존 로그를 반환하고 새 로그를 추가하지 않습니다.
    """

    normalized_status = status if status in _VALID_STATUSES else "info"

    normalized_action_type = action_type.strip() if isinstance(action_type, str) else ""
    if not normalized_action_type:
        normalized_action_type = "unknown"

    normalized_source = source.strip() if isinstance(source, str) else ""
    if not normalized_source:
        normalized_source = "system"

    normalized_dedupe = dedupe_key.strip() if isinstance(dedupe_key, str) else None
    if normalized_dedupe:
        existing = (
            db.query(SessionActivityLog)
            .filter(
                SessionActivityLog.session_id == session_id,
                SessionActivityLog.dedupe_key == normalized_dedupe,
            )
            .order_by(SessionActivityLog.id.desc())
            .first()
        )
        if existing:
            return existing

    row = SessionActivityLog(
        session_id=session_id,
        actor_user_id=actor_user_id,
        actor_character_id=actor_character_id,
        source=normalized_source,
        action_type=normalized_action_type,
        status=normalized_status,
        message=message,
        detail=detail,
        dedupe_key=normalized_dedupe,
    )
    db.add(row)
    return row

