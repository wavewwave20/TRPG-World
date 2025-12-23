#!/usr/bin/env python3
"""
Diagnostic script to help identify AI workflow issues.

Run this script to check:
1. Environment configuration
2. Database connectivity
3. LLM API connectivity
4. Character data validity
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()


def check_environment():
    """Check environment variables."""
    print("=" * 60)
    print("ENVIRONMENT CONFIGURATION")
    print("=" * 60)

    required_vars = {
        "GEMINI_API_KEY": "Google API key for Gemini",
        "SYSTEM_PROMPT_PATH": "Path to system prompt",
        "LLM_MODEL": "LLM model name",
    }

    all_ok = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            # Mask API keys
            if "KEY" in var or "SECRET" in var:
                display_value = value[:8] + "..." if len(value) > 8 else "***"
            else:
                display_value = value
            print(f"✓ {var}: {display_value}")
        else:
            print(f"✗ {var}: NOT SET ({description})")
            all_ok = False

    print()
    return all_ok


def check_system_prompt():
    """Check if system prompt file exists."""
    print("=" * 60)
    print("SYSTEM PROMPT FILE")
    print("=" * 60)

    prompt_path = os.getenv("SYSTEM_PROMPT_PATH", "app/prompts/system_prompt.md")
    full_path = Path(__file__).parent / prompt_path

    if full_path.exists():
        size = full_path.stat().st_size
        print(f"✓ System prompt found: {prompt_path}")
        print(f"  Size: {size} bytes")

        # Read first few lines
        with open(full_path, encoding="utf-8") as f:
            lines = f.readlines()[:3]
            print(f"  First line: {lines[0].strip()[:60]}...")
        print()
        return True
    print(f"✗ System prompt NOT FOUND: {prompt_path}")
    print(f"  Expected at: {full_path}")
    print()
    return False


def check_database():
    """Check database connectivity and data."""
    print("=" * 60)
    print("DATABASE")
    print("=" * 60)

    try:
        from app.database import SessionLocal
        from app.models import Character, GameSession, SessionParticipant

        db = SessionLocal()
        try:
            # Check sessions
            session_count = db.query(GameSession).count()
            active_sessions = db.query(GameSession).filter(GameSession.is_active == True).count()
            print("✓ Database connected")
            print(f"  Total sessions: {session_count}")
            print(f"  Active sessions: {active_sessions}")

            # Check characters
            char_count = db.query(Character).count()
            print(f"  Total characters: {char_count}")

            # Check if there are any active sessions with characters
            if active_sessions > 0:
                session = db.query(GameSession).filter(GameSession.is_active == True).first()
                if session:
                    participants = (
                        db.query(SessionParticipant).filter(SessionParticipant.session_id == session.id).count()
                    )
                    print(f"\n  Sample active session (ID {session.id}):")
                    print(f"    Title: {session.title}")
                    print(f"    Participants: {participants}")

                    # Get characters in this session
                    chars = (
                        db.query(Character)
                        .join(SessionParticipant)
                        .filter(SessionParticipant.session_id == session.id)
                        .all()
                    )

                    if chars:
                        print("    Characters:")
                        for char in chars:
                            print(f"      - {char.name} (ID: {char.id})")
                            print(f"        STR: {char.strength}, DEX: {char.dexterity}, CON: {char.constitution}")
                            print(f"        INT: {char.intelligence}, WIS: {char.wisdom}, CHA: {char.charisma}")
                    else:
                        print("    ⚠ No characters in this session")

            print()
            return True

        finally:
            db.close()

    except Exception as e:
        print(f"✗ Database error: {e}")
        print()
        return False


async def test_ai_service():
    """Test the AI service with sample data."""
    print("=" * 60)
    print("AI SERVICE TEST")
    print("=" * 60)

    try:
        from app.database import SessionLocal
        from app.models import Character, GameSession, SessionParticipant
        from app.schemas import ActionType, PlayerAction
        from app.services.ai_gm_service_v2 import AIGMServiceV2

        db = SessionLocal()
        try:
            # Find an active session with characters
            session = db.query(GameSession).filter(GameSession.is_active == True).first()
            if not session:
                print("⚠ No active sessions found. Create a session first.")
                print()
                return False

            # Get a character from this session
            participant = db.query(SessionParticipant).filter(SessionParticipant.session_id == session.id).first()

            if not participant:
                print(f"⚠ No participants in session {session.id}. Join a session first.")
                print()
                return False

            character = db.query(Character).filter(Character.id == participant.character_id).first()
            if not character:
                print(f"⚠ Character {participant.character_id} not found.")
                print()
                return False

            print("Testing with:")
            print(f"  Session: {session.title} (ID: {session.id})")
            print(f"  Character: {character.name} (ID: {character.id})")
            print()

            # Initialize AI service
            llm_model = os.getenv("LLM_MODEL", "gpt-4o")

            service = AIGMServiceV2(db=db, llm_model=llm_model)

            # Test Phase 1: Action Analysis
            print("Testing Phase 1: Action Analysis...")
            analyses = await service.analyze_actions(
                session_id=session.id,
                player_actions=[
                    PlayerAction(
                        character_id=character.id,
                        action_text="I look around the room carefully.",
                        action_type=ActionType.WISDOM,
                    )
                ],
            )

            print("✓ AI service working!")
            print(f"  Analyses: {len(analyses)}")
            if analyses:
                a = analyses[0]
                print(f"    Modifier: {a.modifier}, DC: {a.difficulty}")
                print(f"    Reasoning: {a.difficulty_reasoning[:100]}...")
            print()
            return True

        finally:
            db.close()

    except Exception as e:
        print(f"✗ Judgment engine error: {e}")
        print()
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all diagnostic checks."""
    print("\n" + "=" * 60)
    print("AI WORKFLOW DIAGNOSTIC TOOL")
    print("=" * 60)
    print()

    results = {
        "Environment": check_environment(),
        "System Prompt": check_system_prompt(),
        "Database": check_database(),
        "AI Service": await test_ai_service(),
    }

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for check, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {check}")

    print()

    if all(results.values()):
        print("✓ All checks passed! AI workflow should be working.")
    else:
        print("✗ Some checks failed. Fix the issues above and try again.")
        print("\nFor more help, see: backend/AI_WORKFLOW_FIX.md")

    print()


if __name__ == "__main__":
    asyncio.run(main())
