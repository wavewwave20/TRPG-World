"""
Tests for session state manager module.

This module tests the dice roll tracking functionality for the 3-phase AI process,
including round initialization, dice roll recording, and state management.

Requirements: 1-B.5, 1.4
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Character, DiceRollState, GameSession, SessionParticipant, User
from app.services.session_state_manager import (
    SessionStateManager,
    check_all_rolled_from_db,
    get_dice_results_from_db,
    get_session_state_manager,
    initialize_round_from_db,
    reset_round_in_db,
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
        world_prompt="A fantasy world",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


@pytest.fixture
def sample_characters(db_session, sample_user):
    """Create sample characters."""
    characters = []
    for i in range(3):
        character = Character(
            user_id=sample_user.id,
            name=f"Character {i + 1}",
            data={"ability_scores": {"STR": 10 + i, "DEX": 12 + i, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10}},
            created_at=datetime.utcnow(),
        )
        db_session.add(character)
        characters.append(character)

    db_session.commit()
    for char in characters:
        db_session.refresh(char)

    return characters


@pytest.fixture
def session_with_participants(db_session, sample_session, sample_characters, sample_user):
    """Create a session with participants."""
    for char in sample_characters:
        participant = SessionParticipant(
            session_id=sample_session.id, user_id=sample_user.id, character_id=char.id, joined_at=datetime.utcnow()
        )
        db_session.add(participant)

    db_session.commit()
    return sample_session


@pytest.fixture
def state_manager():
    """Create a fresh session state manager."""
    return SessionStateManager()


# =============================================================================
# In-Memory State Manager Tests
# =============================================================================


class TestSessionStateManager:
    """Tests for SessionStateManager class."""

    def test_initialize_round(self, state_manager):
        """Test round initialization."""
        session_id = 1
        character_ids = [10, 20, 30]

        round_id = state_manager.initialize_round(session_id, character_ids)

        assert round_id == 1
        assert state_manager.get_pending_characters(session_id) == {10, 20, 30}
        assert state_manager.get_rolled_characters(session_id) == set()
        assert state_manager.check_all_rolled(session_id) is False

    def test_initialize_round_increments_round_id(self, state_manager):
        """Test that round_id increments for each new round."""
        session_id = 1

        round_id_1 = state_manager.initialize_round(session_id, [10])
        round_id_2 = state_manager.initialize_round(session_id, [20])
        round_id_3 = state_manager.initialize_round(session_id, [30])

        assert round_id_1 == 1
        assert round_id_2 == 2
        assert round_id_3 == 3

    def test_initialize_round_with_analyses(self, state_manager):
        """Test round initialization with analysis data."""
        session_id = 1
        character_ids = [10, 20]
        analyses = {10: {"modifier": 3, "difficulty": 15}, 20: {"modifier": -1, "difficulty": 12}}

        state_manager.initialize_round(session_id, character_ids, analyses)

        assert state_manager.get_analysis(session_id, 10) == {"modifier": 3, "difficulty": 15}
        assert state_manager.get_analysis(session_id, 20) == {"modifier": -1, "difficulty": 12}

    def test_record_dice_roll_success(self, state_manager):
        """Test successful dice roll recording."""
        session_id = 1
        state_manager.initialize_round(session_id, [10, 20, 30])

        result = state_manager.record_dice_roll(session_id, 10, 15)

        assert result is True
        assert 10 not in state_manager.get_pending_characters(session_id)
        assert 10 in state_manager.get_rolled_characters(session_id)
        assert state_manager.get_dice_results(session_id)[10] == 15

    def test_record_dice_roll_invalid_session(self, state_manager):
        """Test dice roll recording for non-existent session."""
        result = state_manager.record_dice_roll(999, 10, 15)

        assert result is False

    def test_record_dice_roll_invalid_character(self, state_manager):
        """Test dice roll recording for character not in pending list."""
        session_id = 1
        state_manager.initialize_round(session_id, [10, 20])

        result = state_manager.record_dice_roll(session_id, 30, 15)  # 30 not in list

        assert result is False

    def test_record_dice_roll_duplicate(self, state_manager):
        """Test that duplicate dice rolls are rejected."""
        session_id = 1
        state_manager.initialize_round(session_id, [10, 20])

        # First roll should succeed
        result1 = state_manager.record_dice_roll(session_id, 10, 15)
        assert result1 is True

        # Second roll for same character should fail
        result2 = state_manager.record_dice_roll(session_id, 10, 20)
        assert result2 is False

        # Original result should be preserved
        assert state_manager.get_dice_results(session_id)[10] == 15

    def test_check_all_rolled_false(self, state_manager):
        """Test check_all_rolled returns False when not all have rolled."""
        session_id = 1
        state_manager.initialize_round(session_id, [10, 20, 30])

        state_manager.record_dice_roll(session_id, 10, 15)
        state_manager.record_dice_roll(session_id, 20, 8)

        assert state_manager.check_all_rolled(session_id) is False

    def test_check_all_rolled_true(self, state_manager):
        """Test check_all_rolled returns True when all have rolled."""
        session_id = 1
        state_manager.initialize_round(session_id, [10, 20, 30])

        state_manager.record_dice_roll(session_id, 10, 15)
        state_manager.record_dice_roll(session_id, 20, 8)
        state_manager.record_dice_roll(session_id, 30, 20)

        assert state_manager.check_all_rolled(session_id) is True

    def test_check_all_rolled_invalid_session(self, state_manager):
        """Test check_all_rolled for non-existent session."""
        assert state_manager.check_all_rolled(999) is False

    def test_get_dice_results(self, state_manager):
        """Test getting all dice results."""
        session_id = 1
        state_manager.initialize_round(session_id, [10, 20, 30])

        state_manager.record_dice_roll(session_id, 10, 15)
        state_manager.record_dice_roll(session_id, 20, 8)
        state_manager.record_dice_roll(session_id, 30, 20)

        results = state_manager.get_dice_results(session_id)

        assert results == {10: 15, 20: 8, 30: 20}

    def test_get_dice_results_partial(self, state_manager):
        """Test getting dice results when not all have rolled."""
        session_id = 1
        state_manager.initialize_round(session_id, [10, 20, 30])

        state_manager.record_dice_roll(session_id, 10, 15)

        results = state_manager.get_dice_results(session_id)

        assert results == {10: 15}

    def test_get_dice_results_invalid_session(self, state_manager):
        """Test getting dice results for non-existent session."""
        results = state_manager.get_dice_results(999)

        assert results == {}

    def test_reset_round(self, state_manager):
        """Test round reset."""
        session_id = 1
        state_manager.initialize_round(session_id, [10, 20, 30])
        state_manager.record_dice_roll(session_id, 10, 15)

        result = state_manager.reset_round(session_id)

        assert result is True
        assert state_manager.get_pending_characters(session_id) == set()
        assert state_manager.get_rolled_characters(session_id) == set()
        assert state_manager.get_dice_results(session_id) == {}

    def test_reset_round_invalid_session(self, state_manager):
        """Test reset for non-existent session."""
        result = state_manager.reset_round(999)

        assert result is False

    def test_clear_session(self, state_manager):
        """Test clearing all session state."""
        session_id = 1
        state_manager.initialize_round(session_id, [10, 20])
        state_manager.record_dice_roll(session_id, 10, 15)

        result = state_manager.clear_session(session_id)

        assert result is True
        assert state_manager.get_round_state(session_id) is None

    def test_get_round_state(self, state_manager):
        """Test getting round state."""
        session_id = 1
        state_manager.initialize_round(session_id, [10, 20])

        round_state = state_manager.get_round_state(session_id)

        assert round_state is not None
        assert round_state.round_id == 1
        assert round_state.pending_characters == {10, 20}

    def test_set_analysis(self, state_manager):
        """Test setting analysis data."""
        session_id = 1
        state_manager.initialize_round(session_id, [10])

        result = state_manager.set_analysis(session_id, 10, {"modifier": 5, "difficulty": 18})

        assert result is True
        assert state_manager.get_analysis(session_id, 10) == {"modifier": 5, "difficulty": 18}

    def test_multiple_sessions(self, state_manager):
        """Test managing multiple sessions simultaneously."""
        state_manager.initialize_round(1, [10, 20])
        state_manager.initialize_round(2, [30, 40, 50])

        state_manager.record_dice_roll(1, 10, 15)
        state_manager.record_dice_roll(2, 30, 8)
        state_manager.record_dice_roll(2, 40, 12)

        assert state_manager.get_pending_characters(1) == {20}
        assert state_manager.get_pending_characters(2) == {50}
        assert state_manager.check_all_rolled(1) is False
        assert state_manager.check_all_rolled(2) is False


class TestGetSessionStateManager:
    """Tests for get_session_state_manager singleton."""

    def test_returns_same_instance(self):
        """Test that get_session_state_manager returns the same instance."""
        mgr1 = get_session_state_manager()
        mgr2 = get_session_state_manager()

        assert mgr1 is mgr2


# =============================================================================
# Database-backed Function Tests
# =============================================================================


class TestDatabaseFunctions:
    """Tests for database-backed state management functions."""

    def test_initialize_round_from_db(self, db_session, session_with_participants, sample_characters):
        """Test initializing round state in database."""
        session_id = session_with_participants.id
        round_id = 1

        result = initialize_round_from_db(db_session, session_id, round_id)

        assert result is True

        # Verify records were created
        states = (
            db_session.query(DiceRollState)
            .filter(DiceRollState.session_id == session_id, DiceRollState.round_id == round_id)
            .all()
        )

        assert len(states) == len(sample_characters)
        for state in states:
            assert state.has_rolled is False
            assert state.dice_result is None

    def test_check_all_rolled_from_db_false(self, db_session, session_with_participants, sample_characters):
        """Test check_all_rolled_from_db returns False when not all rolled."""
        session_id = session_with_participants.id
        round_id = 1

        # Initialize round
        initialize_round_from_db(db_session, session_id, round_id)

        # Mark only one as rolled
        state = (
            db_session.query(DiceRollState)
            .filter(DiceRollState.session_id == session_id, DiceRollState.round_id == round_id)
            .first()
        )
        state.has_rolled = True
        state.dice_result = 15
        db_session.commit()

        result = check_all_rolled_from_db(db_session, session_id, round_id)

        assert result is False

    def test_check_all_rolled_from_db_true(self, db_session, session_with_participants, sample_characters):
        """Test check_all_rolled_from_db returns True when all rolled."""
        session_id = session_with_participants.id
        round_id = 1

        # Initialize round
        initialize_round_from_db(db_session, session_id, round_id)

        # Mark all as rolled
        states = (
            db_session.query(DiceRollState)
            .filter(DiceRollState.session_id == session_id, DiceRollState.round_id == round_id)
            .all()
        )

        for i, state in enumerate(states):
            state.has_rolled = True
            state.dice_result = 10 + i
        db_session.commit()

        result = check_all_rolled_from_db(db_session, session_id, round_id)

        assert result is True

    def test_get_dice_results_from_db(self, db_session, session_with_participants, sample_characters):
        """Test getting dice results from database."""
        session_id = session_with_participants.id
        round_id = 1

        # Initialize round
        initialize_round_from_db(db_session, session_id, round_id)

        # Mark some as rolled
        states = (
            db_session.query(DiceRollState)
            .filter(DiceRollState.session_id == session_id, DiceRollState.round_id == round_id)
            .all()
        )

        states[0].has_rolled = True
        states[0].dice_result = 15
        states[1].has_rolled = True
        states[1].dice_result = 8
        db_session.commit()

        results = get_dice_results_from_db(db_session, session_id, round_id)

        assert len(results) == 2
        dice_values = [r["dice_result"] for r in results]
        assert 15 in dice_values
        assert 8 in dice_values

    def test_reset_round_in_db(self, db_session, session_with_participants, sample_characters):
        """Test resetting round state in database."""
        session_id = session_with_participants.id
        round_id = 1

        # Initialize round
        initialize_round_from_db(db_session, session_id, round_id)

        # Verify records exist
        count_before = (
            db_session.query(DiceRollState)
            .filter(DiceRollState.session_id == session_id, DiceRollState.round_id == round_id)
            .count()
        )
        assert count_before > 0

        # Reset
        result = reset_round_in_db(db_session, session_id, round_id)

        assert result is True

        # Verify records were deleted
        count_after = (
            db_session.query(DiceRollState)
            .filter(DiceRollState.session_id == session_id, DiceRollState.round_id == round_id)
            .count()
        )
        assert count_after == 0
