"""Utilities for resolving the current open act in a session."""

from sqlalchemy.orm import Session

from app.models import StoryAct, StoryLog


def resolve_current_open_act(db: Session, session_id: int) -> StoryAct | None:
    """Resolve a stable current open act for a session.

    When multiple open acts exist (data drift/manual edits), prefer the act
    referenced by the most recent story log. If none of the open acts are
    referenced, fall back to the newest open act by started_at/id.
    """
    open_acts = (
        db.query(StoryAct)
        .filter(StoryAct.session_id == session_id, StoryAct.ended_at.is_(None))
        .order_by(StoryAct.started_at.desc(), StoryAct.id.desc())
        .all()
    )
    if not open_acts:
        return None

    open_act_ids = [act.id for act in open_acts]
    latest_log = (
        db.query(StoryLog.act_id)
        .filter(
            StoryLog.session_id == session_id,
            StoryLog.act_id.isnot(None),
            StoryLog.act_id.in_(open_act_ids),
        )
        .order_by(StoryLog.created_at.desc(), StoryLog.id.desc())
        .first()
    )

    if latest_log and latest_log[0] is not None:
        act_by_id = {act.id: act for act in open_acts}
        resolved = act_by_id.get(latest_log[0])
        if resolved:
            return resolved

    return open_acts[0]
