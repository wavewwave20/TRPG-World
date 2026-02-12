#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$ROOT_DIR"

docker compose exec -T backend bash -lc "PYTHONPATH=/app python -c \"from app.database import SessionLocal; from app.models import User, Character, GameSession, SessionParticipant, StoryLog, StoryAct, ActionJudgment, DiceRollState, CharacterGrowthLog; db=SessionLocal();\ntry:\n  db.query(CharacterGrowthLog).delete();\n  db.query(DiceRollState).delete();\n  db.query(ActionJudgment).delete();\n  db.query(StoryAct).delete();\n  db.query(StoryLog).delete();\n  db.query(SessionParticipant).delete();\n  db.query(GameSession).delete();\n  uids=[u.id for u in db.query(User).filter(User.username.in_(['user1','user2'])).all()];\n  if uids: db.query(Character).filter(Character.user_id.in_(uids)).delete(synchronize_session=False);\n  db.commit();\n  print('reset done');\nfinally:\n  db.close()\""
