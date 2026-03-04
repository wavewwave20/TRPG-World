#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$ROOT_DIR"

docker compose exec -T backend python - <<'PY'
from app.database import SessionLocal
from app.models import ActionJudgment, Character, CharacterGrowthLog, DiceRollState, GameSession, SessionParticipant, StoryAct, StoryLog, User

db = SessionLocal()
try:
    db.query(CharacterGrowthLog).delete()
    db.query(DiceRollState).delete()
    db.query(ActionJudgment).delete()
    db.query(StoryAct).delete()
    db.query(StoryLog).delete()
    db.query(SessionParticipant).delete()
    db.query(GameSession).delete()
    user_ids = [u.id for u in db.query(User).filter(User.username.in_(["user1", "user2"])).all()]
    if user_ids:
        db.query(Character).filter(Character.user_id.in_(user_ids)).delete(synchronize_session=False)
    db.commit()
    print("reset done")
finally:
    db.close()
PY
