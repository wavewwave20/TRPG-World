"""
Context loader for AI Game Master system.

This module provides functions to load game context from the database,
including session information, characters, and story history.

The context loader handles:
- Session information retrieval
- Character list retrieval (session-associated)
- Story history retrieval (all entries, ordered by created_at desc)
- Invalid data handling (graceful degradation)
"""

import logging

from sqlalchemy.orm import Session

from app.models import Character, GameSession, SessionParticipant, StoryAct, StoryLog
from app.schemas import CharacterSheet, GameContext, StoryActInfo, StoryLogEntry
from app.services.act_resolver import resolve_current_open_act
from app.services.character_state import normalize_inventory_items, normalize_statuses

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
    - Recent story history (all available entries)

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
        - 7.2: Story history size limitation removed (load all)
    """
    logger.info(f"Loading game context for session {session_id}")

    try:
        # Load session information
        session = _load_session(db, session_id)

        # Load characters in this session
        characters = _load_characters(db, session_id)

        # Load current act info
        current_act = _load_current_act(db, session_id)

        # Load story history: 현재 막이 있으면 해당 막의 전체 스토리, 없으면 세션 전체 로그 폴백
        if current_act:
            story_history = load_act_story_history(db, session_id, current_act.id)
        else:
            story_history = _load_story_history(db, session_id)

        # Build game context
        game_context = GameContext(
            session_id=session_id,
            world_prompt=session.world_prompt,
            system_prompt=system_prompt,
            characters=characters,
            story_history=story_history,
            ai_summary=session.ai_summary,
            current_act=current_act,
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

    This function retrieves all story log entries for the session,
    ordered by created_at in descending order (newest first).

    Args:
        db: Database session
        session_id: ID of the game session

    Returns:
        List[StoryLogEntry]: List of story log entries

    Requirements:
        - 7.1: Order by created_at desc
        - 7.2: Story history size limitation removed (load all)
    """
    # Query story logs: all entries, ordered by created_at desc
    story_logs_db = (
        db.query(StoryLog).filter(StoryLog.session_id == session_id).order_by(StoryLog.created_at.desc()).all()
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

    # Extract ability scores - support both top-level keys (new) and nested ability_scores (legacy)
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

    statuses = normalize_statuses(data)
    inventory = normalize_inventory_items(data.get("inventory", []))

    return CharacterSheet(
        id=character.id,
        name=character.name,
        age=data.get("age"),
        race=data.get("race"),
        concept=data.get("concept"),
        strength=data.get("strength") or ability_scores.get("STR", 10),
        dexterity=data.get("dexterity") or ability_scores.get("DEX", 10),
        constitution=data.get("constitution") or ability_scores.get("CON", 10),
        intelligence=data.get("intelligence") or ability_scores.get("INT", 10),
        wisdom=data.get("wisdom") or ability_scores.get("WIS", 10),
        charisma=data.get("charisma") or ability_scores.get("CHA", 10),
        skills=skills,
        weaknesses=weaknesses,
        status_effects=status_effects,
        statuses=statuses,
        inventory=inventory,
    )


def extract_starting_situation(world_prompt: str) -> str | None:
    """세계관 프롬프트에서 '시작 상황' 섹션의 텍스트를 추출합니다.

    '시작 상황:' 헤더 이후의 모든 텍스트를 반환합니다.
    헤더가 없으면 None을 반환합니다.

    Args:
        world_prompt: 세계관 프롬프트 전체 텍스트

    Returns:
        str | None: 시작 상황 텍스트 또는 None
    """
    import re

    pattern = r"시작\s*상황\s*:"
    match = re.search(pattern, world_prompt)
    if not match:
        return None

    text = world_prompt[match.end() :].strip()
    return text if text else None


def _load_current_act(db: Session, session_id: int) -> StoryActInfo | None:
    """현재 진행 중인 막 정보를 로드합니다.

    Args:
        db: 데이터베이스 세션
        session_id: 게임 세션 ID

    Returns:
        StoryActInfo | None: 현재 막 정보 또는 None
    """
    act = resolve_current_open_act(db, session_id)

    if not act:
        return None

    return StoryActInfo(
        id=act.id,
        act_number=act.act_number,
        title=act.title,
        subtitle=act.subtitle,
        started_at=act.started_at.isoformat(),
    )


def get_current_act(db: Session, session_id: int) -> StoryActInfo | None:
    """외부에서 호출 가능한 현재 막 정보 조회.

    Args:
        db: 데이터베이스 세션
        session_id: 게임 세션 ID

    Returns:
        StoryActInfo | None: 현재 막 정보 또는 None
    """
    return _load_current_act(db, session_id)


def get_all_acts(db: Session, session_id: int) -> list[StoryActInfo]:
    """세션의 모든 막 정보를 조회합니다.

    Args:
        db: 데이터베이스 세션
        session_id: 게임 세션 ID

    Returns:
        list[StoryActInfo]: 모든 막 정보 목록
    """
    acts = db.query(StoryAct).filter(StoryAct.session_id == session_id).order_by(StoryAct.act_number).all()

    return [
        StoryActInfo(
            id=act.id,
            act_number=act.act_number,
            title=act.title,
            subtitle=act.subtitle,
            started_at=act.started_at.isoformat(),
        )
        for act in acts
    ]


def load_act_story_history(db: Session, session_id: int, act_id: int) -> list[StoryLogEntry]:
    """특정 막에 속하는 스토리 로그를 로드합니다.

    Args:
        db: 데이터베이스 세션
        session_id: 게임 세션 ID
        act_id: 막 ID

    Returns:
        list[StoryLogEntry]: 해당 막의 스토리 로그 목록
    """
    logs = (
        db.query(StoryLog)
        .filter(StoryLog.session_id == session_id, StoryLog.act_id == act_id)
        .order_by(StoryLog.created_at.asc())
        .all()
    )

    return [StoryLogEntry(role=log.role, content=log.content, created_at=log.created_at) for log in logs]
