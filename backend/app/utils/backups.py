import json
import os
from datetime import datetime

from app.database import SessionLocal
from app.models import GameSession, StoryLog
from app.utils.timezone import to_kst_iso


def backup_session(session_id: int) -> str | None:
    """Backup a session's metadata and story logs to a JSON file.

    Returns the absolute filepath written, or None if session not found.
    """
    db = SessionLocal()
    try:
        session = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not session:
            return None
        logs = db.query(StoryLog).filter(StoryLog.session_id == session_id).order_by(StoryLog.created_at.asc()).all()

        data = {
            "session": {
                "id": session.id,
                "title": session.title,
                "host_user_id": session.host_user_id,
                "is_active": session.is_active,
                "created_at": to_kst_iso(session.created_at),
            },
            "story_logs": [
                {
                    "id": log.id,
                    "role": log.role,
                    "content": log.content,
                    "created_at": to_kst_iso(log.created_at),
                }
                for log in logs
            ],
            "exported_at": to_kst_iso(datetime.utcnow()),
        }

        # backups directory next to app/
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        backups_dir = os.path.join(base_dir, "backups")
        os.makedirs(backups_dir, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"session_{session_id}_{ts}.json"
        filepath = os.path.join(backups_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath
    finally:
        db.close()
