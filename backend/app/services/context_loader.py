"""
Context loader for AI Game Master system.

This module provides functions to load game context from the database,
including session information, characters, and story history.

The context loader handles:
- Session information retrieval
- Character list retrieval (session-associated)
- Story history retrieval (most recent 20, ordered by created_at desc)
- Invalid data handling (graceful degradation)
"""

import logging

from sqlalchemy.orm import Session

from app.models import Character, GameSession, SessionParticipant, StoryLog
from app.schemas import CharacterSheet, GameContext, StoryLogEntry

logger = logging.getLogger("ai_gm.context_loader")


class ContextLoadError(Exception):
    """컨텍스트 로딩 실패 시 발생하는 예외."""

    pass


def load_game_context(db: Session, session_id: int, system_prompt: str) -> GameContext:
    """
    Load complete game context for AI generation.

    This function retrieves all necessary information for AI prompt construction:
    - Session information and world prompt
    - All characters participating in the session
    - Recent story history (max 20 entries, most recent first)

    The function handles invalid character data gracefully by skipping
    problematic characters and continuing with valid ones.

    Args:
        db: Database session
        session_id: ID of the game session
        system_prompt: TRPG system rules from markdown file

    Returns:
        GameContext: Complete context with all loaded data

    Raises:
        ContextLoadError: If session not found or critical data missing

    Requirements:
        - 6.1: Retrieve all characters associated with session
        - 6.4: Handle invalid character data gracefully
        - 7.1: Retrieve story logs ordered by created_at desc
        - 7.2: Limit story history to 20 most recent entries
    """
    logger.info(f"Loading game context for session {session_id}")

    try:
        # Load session information
        session = _load_session(db, session_id)

        # Load characters in this session
        characters = _load_characters(db, session_id)

        # Load story history
        story_history = _load_story_history(db, session_id)

        # Build game context
        game_context = GameContext(
            session_id=session_id,
            world_prompt=session.world_prompt,
            system_prompt=system_prompt,
            characters=characters,
            story_history=story_history,
            ai_summary=session.ai_summary,
        )

        logger.info(f"Context loaded successfully: {len(characters)} characters, {len(story_history)} history entries")

        return game_context

    except Exception as e:
        logger.error(f"Failed to load game context: {e}", exc_info=True)
        raise ContextLoadError(f"Failed to load game context: {e!s}") from e


def _load_session(db: Session, session_id: int) -> GameSession:
    """
    Load session information from database.

    Args:
        db: Database session
        session_id: ID of the game session

    Returns:
        GameSession: Session ORM object

    Raises:
        ContextLoadError: If session not found
    """
    session = db.query(GameSession).filter(GameSession.id == session_id).first()

    if not session:
        raise ContextLoadError(f"Session {session_id} not found")

    logger.debug(f"Loaded session {session_id}: {session.title}")

    return session


def _load_characters(db: Session, session_id: int) -> list[CharacterSheet]:
    """
    Load all characters participating in the session.

    This function:
    1. Queries session_participants to get character IDs
    2. Loads character data from characters table
    3. Converts to CharacterSheet objects
    4. Handles invalid character data gracefully (skips and continues)

    Args:
        db: Database session
        session_id: ID of the game session

    Returns:
        List[CharacterSheet]: List of character sheets (may be empty)

    Requirements:
        - 6.1: Retrieve all characters associated with session
        - 6.4: Handle invalid character data gracefully
    """
    # Get participant records
    participants = db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id).all()

    if not participants:
        logger.warning(f"No participants found for session {session_id}")
        return []

    # Get character IDs
    character_ids = [p.character_id for p in participants]

    # Load characters
    characters_db = db.query(Character).filter(Character.id.in_(character_ids)).all()

    # Convert to CharacterSheet objects
    characters = []
    for char in characters_db:
        try:
            char_sheet = _character_to_sheet(char)
            characters.append(char_sheet)
            logger.debug(f"Loaded character {char.id}: {char.name}")
        except Exception as e:
            # Requirement 6.4: Handle invalid data gracefully
            logger.warning(f"Failed to load character {char.id}: {e}. Skipping this character.")
            # Continue with other characters
            continue

    logger.info(f"Loaded {len(characters)} characters out of {len(characters_db)} total")

    return characters


def _load_story_history(db: Session, session_id: int) -> list[StoryLogEntry]:
    """
    Load recent story history for the session.

    This function retrieves the most recent 20 story log entries,
    ordered by created_at in descending order (newest first).

    Args:
        db: Database session
        session_id: ID of the game session

    Returns:
        List[StoryLogEntry]: List of story log entries (max 20)

    Requirements:
        - 7.1: Order by created_at desc
        - 7.2: Limit to 20 most recent entries
    """
    # Query story logs: most recent 20, ordered by created_at desc
    story_logs_db = (
        db.query(StoryLog)
        .filter(StoryLog.session_id == session_id)
        .order_by(StoryLog.created_at.desc())
        .limit(20)
        .all()
    )

    # Convert to StoryLogEntry objects
    story_history = [
        StoryLogEntry(role=log.role, content=log.content, created_at=log.created_at) for log in story_logs_db
    ]

    logger.debug(f"Loaded {len(story_history)} story log entries")

    return story_history


def _character_to_sheet(character: Character) -> CharacterSheet:
    """
    Convert database Character to CharacterSheet.

    Extracts character data from the JSON field and creates
    a structured CharacterSheet object for AI context.

    Args:
        character: Character ORM object

    Returns:
        CharacterSheet: Pydantic model for AI context

    Raises:
        ValueError: If character data is invalid or missing required fields
    """
    data = character.data or {}

    # Extract ability scores
    ability_scores = data.get("ability_scores", {})

    # Extract skills - convert dict to list of dicts
    skills_raw = data.get("skills", {})
    skills = []
    if isinstance(skills_raw, dict):
        # Convert dict format to list of dicts
        for skill_name, skill_value in skills_raw.items():
            if isinstance(skill_value, dict):
                # Already in dict format with additional fields
                skills.append({"name": skill_name, **skill_value})
            else:
                # Simple value (e.g., bonus number)
                skills.append({"name": skill_name, "bonus": skill_value})
    elif isinstance(skills_raw, list):
        # Already in list format
        skills = skills_raw

    # Extract weaknesses (list of strings)
    weaknesses = data.get("weaknesses", [])

    # Extract status effects (list of strings or dicts)
    status_effects_raw = data.get("status_effects", [])
    status_effects = []
    for effect in status_effects_raw:
        if isinstance(effect, str):
            status_effects.append(effect)
        elif isinstance(effect, dict):
            # If effect is a dict, use its name or description
            status_effects.append(effect.get("name") or effect.get("description", "Unknown effect"))

    return CharacterSheet(
        id=character.id,
        name=character.name,
        age=data.get("age"),
        race=data.get("race"),
        concept=data.get("concept"),
        strength=ability_scores.get("STR", 10),
        dexterity=ability_scores.get("DEX", 10),
        constitution=ability_scores.get("CON", 10),
        intelligence=ability_scores.get("INT", 10),
        wisdom=ability_scores.get("WIS", 10),
        charisma=ability_scores.get("CHA", 10),
        skills=skills,
        weaknesses=weaknesses,
        status_effects=status_effects,
    )
