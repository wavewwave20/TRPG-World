#!/usr/bin/env python3
"""Add a character to session 1 for testing."""

import sys

from app.database import SessionLocal
from app.models import Character, SessionParticipant

db = SessionLocal()

try:
    # Get first character
    char = db.query(Character).first()

    if not char:
        print("No characters found in database")
        sys.exit(1)

    # Check if already a participant
    existing = (
        db.query(SessionParticipant)
        .filter(SessionParticipant.session_id == 1, SessionParticipant.character_id == char.id)
        .first()
    )

    if existing:
        print(f"Character {char.name} is already in session 1")
    else:
        # Add as participant
        participant = SessionParticipant(session_id=1, character_id=char.id, user_id=char.user_id)
        db.add(participant)
        db.commit()
        print(f"Added character {char.name} (ID: {char.id}) to session 1")

finally:
    db.close()
