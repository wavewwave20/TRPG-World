"""
Tests for context loader module.

This module tests the game context loading functionality,
including session retrieval, character loading, and story history.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Character, GameSession, SessionParticipant, StoryLog, User
from app.schemas import CharacterSheet
from app.services.context_loader import (
    ContextLoadError,
    _character_to_sheet,
    _load_characters,
    _load_session,
    _load_story_history,
    load_game_context,
)

# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_user(db_session):
    """Create a sample user."""
    user = User(username="testuser", password="hashed_password", created_at=datetime.utcnow())
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_session(db_session, sample_user):
    """Create a sample game session."""
    session = GameSession(
        host_user_id=sample_user.id,
        title="Test Session",
        world_prompt="A fantasy world with magic and dragons",
        ai_summary=None,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


@pytest.fixture
def sample_character(db_session, sample_user):
    """Create a sample character."""
    character = Character(
        user_id=sample_user.id,
        name="Test Hero",
        data={
            "age": 25,
            "race": "Human",
            "concept": "Brave warrior",
            "ability_scores": {"STR": 16, "DEX": 14, "CON": 15, "INT": 10, "WIS": 12, "CHA": 13},
            "skills": {"Athletics": 5, "Perception": 3},
            "weaknesses": ["Fear of heights"],
            "status_effects": ["Blessed", {"name": "Haste", "duration": 3}],
        },
        created_at=datetime.utcnow(),
    )
    db_session.add(character)
    db_session.commit()
    db_session.refresh(character)
    return character


def test_load_session_success(db_session, sample_session):
    """Test successful session loading."""
    loaded_session = _load_session(db_session, sample_session.id)

    assert loaded_session.id == sample_session.id
    assert loaded_session.title == "Test Session"
    assert loaded_session.world_prompt == "A fantasy world with magic and dragons"


def test_load_session_not_found(db_session):
    """Test session loading with non-existent session."""
    with pytest.raises(ContextLoadError, match="Session 999 not found"):
        _load_session(db_session, 999)


def test_load_characters_success(db_session, sample_session, sample_character):
    """Test successful character loading."""
    # Add character to session
    participant = SessionParticipant(
        session_id=sample_session.id,
        user_id=sample_character.user_id,
        character_id=sample_character.id,
        joined_at=datetime.utcnow(),
    )
    db_session.add(participant)
    db_session.commit()

    # Load characters
    characters = _load_characters(db_session, sample_session.id)

    assert len(characters) == 1
    assert characters[0].id == sample_character.id
    assert characters[0].name == "Test Hero"
    assert characters[0].strength == 16
    assert characters[0].dexterity == 14


def test_load_characters_empty_session(db_session, sample_session):
    """Test character loading with no participants."""
    characters = _load_characters(db_session, sample_session.id)

    assert len(characters) == 0


def test_load_characters_invalid_data(db_session, sample_session, sample_user):
    """Test character loading with invalid character data."""
    # Create character with invalid data
    bad_character = Character(
        user_id=sample_user.id,
        name="Bad Character",
        data=None,  # Invalid: no data
        created_at=datetime.utcnow(),
    )
    db_session.add(bad_character)
    db_session.commit()

    # Add to session
    participant = SessionParticipant(
        session_id=sample_session.id, user_id=sample_user.id, character_id=bad_character.id, joined_at=datetime.utcnow()
    )
    db_session.add(participant)
    db_session.commit()

    # Should handle gracefully and return empty list
    characters = _load_characters(db_session, sample_session.id)

    # Character with invalid data should be skipped
    assert len(characters) == 1  # Still creates a character with defaults


def test_load_story_history_success(db_session, sample_session):
    """Test successful story history loading."""
    # Create story logs
    base_time = datetime.utcnow()
    for i in range(5):
        log = StoryLog(
            session_id=sample_session.id,
            role="USER" if i % 2 == 0 else "AI",
            content=f"Story entry {i}",
            created_at=base_time + timedelta(minutes=i),
        )
        db_session.add(log)
    db_session.commit()

    # Load history
    history = _load_story_history(db_session, sample_session.id)

    assert len(history) == 5
    # Should be ordered by created_at desc (newest first)
    assert history[0].content == "Story entry 4"
    assert history[4].content == "Story entry 0"


def test_load_story_history_limit_20(db_session, sample_session):
    """Test story history limit of 20 entries."""
    # Create 25 story logs
    base_time = datetime.utcnow()
    for i in range(25):
        log = StoryLog(
            session_id=sample_session.id,
            role="USER" if i % 2 == 0 else "AI",
            content=f"Story entry {i}",
            created_at=base_time + timedelta(minutes=i),
        )
        db_session.add(log)
    db_session.commit()

    # Load history
    history = _load_story_history(db_session, sample_session.id)

    # Should only return 20 most recent
    assert len(history) == 20
    # Should be newest first
    assert history[0].content == "Story entry 24"
    assert history[19].content == "Story entry 5"


def test_load_story_history_empty(db_session, sample_session):
    """Test story history loading with no logs."""
    history = _load_story_history(db_session, sample_session.id)

    assert len(history) == 0


def test_character_to_sheet_success(sample_character):
    """Test character to sheet conversion."""
    sheet = _character_to_sheet(sample_character)

    assert isinstance(sheet, CharacterSheet)
    assert sheet.id == sample_character.id
    assert sheet.name == "Test Hero"
    assert sheet.age == 25
    assert sheet.race == "Human"
    assert sheet.concept == "Brave warrior"
    assert sheet.strength == 16
    assert sheet.dexterity == 14
    assert sheet.constitution == 15
    assert sheet.intelligence == 10
    assert sheet.wisdom == 12
    assert sheet.charisma == 13
    # Skills are now a list of dicts
    assert len(sheet.skills) == 2
    skill_names = [s["name"] for s in sheet.skills]
    assert "Athletics" in skill_names
    assert "Perception" in skill_names
    assert sheet.weaknesses == ["Fear of heights"]
    assert "Blessed" in sheet.status_effects
    assert "Haste" in sheet.status_effects


def test_character_to_sheet_defaults(db_session, sample_user):
    """Test character to sheet conversion with missing data."""
    character = Character(
        user_id=sample_user.id,
        name="Minimal Character",
        data={},  # Empty data
        created_at=datetime.utcnow(),
    )
    db_session.add(character)
    db_session.commit()
    db_session.refresh(character)

    sheet = _character_to_sheet(character)

    assert sheet.name == "Minimal Character"
    assert sheet.age is None
    assert sheet.race is None
    assert sheet.concept is None
    # Should use defaults for ability scores
    assert sheet.strength == 10
    assert sheet.dexterity == 10
    assert sheet.constitution == 10
    assert sheet.intelligence == 10
    assert sheet.wisdom == 10
    assert sheet.charisma == 10
    # Skills are now a list, not a dict
    assert sheet.skills == []
    assert sheet.weaknesses == []
    assert sheet.status_effects == []


def test_load_game_context_success(db_session, sample_session, sample_character):
    """Test complete game context loading."""
    # Add character to session
    participant = SessionParticipant(
        session_id=sample_session.id,
        user_id=sample_character.user_id,
        character_id=sample_character.id,
        joined_at=datetime.utcnow(),
    )
    db_session.add(participant)

    # Add story logs
    for i in range(3):
        log = StoryLog(
            session_id=sample_session.id,
            role="USER" if i % 2 == 0 else "AI",
            content=f"Story {i}",
            created_at=datetime.utcnow() + timedelta(minutes=i),
        )
        db_session.add(log)
    db_session.commit()

    # Load context
    system_prompt = "Test system prompt"
    context = load_game_context(db_session, sample_session.id, system_prompt)

    assert context.session_id == sample_session.id
    assert context.world_prompt == "A fantasy world with magic and dragons"
    assert context.system_prompt == "Test system prompt"
    assert len(context.characters) == 1
    assert context.characters[0].name == "Test Hero"
    assert len(context.story_history) == 3
    assert context.ai_summary is None


def test_load_game_context_session_not_found(db_session):
    """Test game context loading with non-existent session."""
    with pytest.raises(ContextLoadError, match="Session 999 not found"):
        load_game_context(db_session, 999, "Test prompt")


def test_load_game_context_with_ai_summary(db_session, sample_session, sample_character):
    """Test game context loading with AI summary."""
    # Update session with AI summary
    sample_session.ai_summary = "Previous adventures summary"
    db_session.commit()

    # Add character to session
    participant = SessionParticipant(
        session_id=sample_session.id,
        user_id=sample_character.user_id,
        character_id=sample_character.id,
        joined_at=datetime.utcnow(),
    )
    db_session.add(participant)
    db_session.commit()

    # Load context
    context = load_game_context(db_session, sample_session.id, "Test prompt")

    assert context.ai_summary == "Previous adventures summary"
