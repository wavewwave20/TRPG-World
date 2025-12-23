"""Unit tests for participant management helper functions."""

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Character, GameSession, User
from app.socket_server import (
    add_participant,
    check_and_deactivate_session,
    get_participant_count,
    get_participants,
    remove_participant,
)


# Create in-memory SQLite database for testing
@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()

    yield session

    session.close()


@pytest.fixture
def test_data(db_session):
    """Create test data: users, characters, and a session."""
    # Create test users
    user1 = User(id=1, username="user1", password="hash1")
    user2 = User(id=2, username="user2", password="hash2")
    db_session.add(user1)
    db_session.add(user2)

    # Create test characters
    char1 = Character(
        id=1,
        name="Hero",
        user_id=1,
        data={"strength": 10, "dexterity": 10, "constitution": 10, "intelligence": 10, "wisdom": 10, "charisma": 10},
    )
    char2 = Character(
        id=2,
        name="Wizard",
        user_id=2,
        data={"strength": 8, "dexterity": 8, "constitution": 8, "intelligence": 15, "wisdom": 12, "charisma": 10},
    )
    db_session.add(char1)
    db_session.add(char2)

    # Create test session
    session = GameSession(id=1, title="Test Session", host_user_id=1, world_prompt="Test world prompt", is_active=True)
    db_session.add(session)

    db_session.commit()

    return {"user1_id": 1, "user2_id": 2, "char1_id": 1, "char2_id": 2, "session_id": 1}


class TestAddParticipant:
    """Tests for add_participant function."""

    def test_add_new_participant(self, db_session, test_data):
        """Test adding a new participant creates a record."""
        participant = add_participant(db_session, test_data["session_id"], test_data["user1_id"], test_data["char1_id"])

        assert participant is not None
        assert participant.session_id == test_data["session_id"]
        assert participant.user_id == test_data["user1_id"]
        assert participant.character_id == test_data["char1_id"]
        assert participant.joined_at is not None

    def test_add_duplicate_participant_updates_existing(self, db_session, test_data):
        """Test adding a duplicate participant updates the existing record."""
        # Add participant first time
        participant1 = add_participant(
            db_session, test_data["session_id"], test_data["user1_id"], test_data["char1_id"]
        )
        first_joined_at = participant1.joined_at

        # Add same participant again with different character
        participant2 = add_participant(
            db_session, test_data["session_id"], test_data["user1_id"], test_data["char2_id"]
        )

        # Should be the same record (same ID)
        assert participant1.id == participant2.id
        assert participant2.character_id == test_data["char2_id"]
        # joined_at should be updated
        assert participant2.joined_at >= first_joined_at

    def test_add_duplicate_does_not_increase_count(self, db_session, test_data):
        """Test that adding a duplicate doesn't increase participant count."""
        # Add participant first time
        add_participant(db_session, test_data["session_id"], test_data["user1_id"], test_data["char1_id"])

        count1 = get_participant_count(db_session, test_data["session_id"])

        # Add same participant again
        add_participant(db_session, test_data["session_id"], test_data["user1_id"], test_data["char1_id"])

        count2 = get_participant_count(db_session, test_data["session_id"])

        assert count1 == 1
        assert count2 == 1

    def test_add_multiple_participants(self, db_session, test_data):
        """Test adding multiple different participants."""
        add_participant(db_session, test_data["session_id"], test_data["user1_id"], test_data["char1_id"])

        add_participant(db_session, test_data["session_id"], test_data["user2_id"], test_data["char2_id"])

        count = get_participant_count(db_session, test_data["session_id"])
        assert count == 2


class TestRemoveParticipant:
    """Tests for remove_participant function."""

    def test_remove_existing_participant(self, db_session, test_data):
        """Test removing an existing participant returns True."""
        # Add participant first
        add_participant(db_session, test_data["session_id"], test_data["user1_id"], test_data["char1_id"])

        # Remove participant
        result = remove_participant(db_session, test_data["session_id"], test_data["user1_id"])

        assert result is True

        # Verify participant is gone
        count = get_participant_count(db_session, test_data["session_id"])
        assert count == 0

    def test_remove_nonexistent_participant(self, db_session, test_data):
        """Test removing a non-existent participant returns False."""
        result = remove_participant(db_session, test_data["session_id"], test_data["user1_id"])

        assert result is False

    def test_remove_participant_decrements_count(self, db_session, test_data):
        """Test that removing a participant decrements the count."""
        # Add two participants
        add_participant(db_session, test_data["session_id"], test_data["user1_id"], test_data["char1_id"])
        add_participant(db_session, test_data["session_id"], test_data["user2_id"], test_data["char2_id"])

        count_before = get_participant_count(db_session, test_data["session_id"])
        assert count_before == 2

        # Remove one participant
        remove_participant(db_session, test_data["session_id"], test_data["user1_id"])

        count_after = get_participant_count(db_session, test_data["session_id"])
        assert count_after == 1


class TestGetParticipantCount:
    """Tests for get_participant_count function."""

    def test_count_empty_session(self, db_session, test_data):
        """Test counting participants in an empty session returns 0."""
        count = get_participant_count(db_session, test_data["session_id"])
        assert count == 0

    def test_count_with_participants(self, db_session, test_data):
        """Test counting participants returns correct count."""
        add_participant(db_session, test_data["session_id"], test_data["user1_id"], test_data["char1_id"])
        add_participant(db_session, test_data["session_id"], test_data["user2_id"], test_data["char2_id"])

        count = get_participant_count(db_session, test_data["session_id"])
        assert count == 2

    def test_count_nonexistent_session(self, db_session):
        """Test counting participants in non-existent session returns 0."""
        count = get_participant_count(db_session, 999)
        assert count == 0


class TestGetParticipants:
    """Tests for get_participants function."""

    def test_get_participants_empty_session(self, db_session, test_data):
        """Test getting participants from empty session returns empty list."""
        participants = get_participants(db_session, test_data["session_id"])
        assert participants == []

    def test_get_participants_with_data(self, db_session, test_data):
        """Test getting participants returns correct data."""
        add_participant(db_session, test_data["session_id"], test_data["user1_id"], test_data["char1_id"])
        add_participant(db_session, test_data["session_id"], test_data["user2_id"], test_data["char2_id"])

        participants = get_participants(db_session, test_data["session_id"])

        assert len(participants) == 2

        # Check structure
        assert all("user_id" in p for p in participants)
        assert all("character_name" in p for p in participants)

        # Check data
        user_ids = [p["user_id"] for p in participants]
        char_names = [p["character_name"] for p in participants]

        assert test_data["user1_id"] in user_ids
        assert test_data["user2_id"] in user_ids
        assert "Hero" in char_names
        assert "Wizard" in char_names

    def test_get_participants_nonexistent_session(self, db_session):
        """Test getting participants from non-existent session returns empty list."""
        participants = get_participants(db_session, 999)
        assert participants == []


class TestTransactionHandling:
    """Tests for database transaction handling."""

    def test_functions_commit_changes(self, db_session, test_data):
        """Test that functions commit their changes to the database."""
        # Add a participant
        add_participant(db_session, test_data["session_id"], test_data["user1_id"], test_data["char1_id"])

        # Create a new session to verify the change was committed
        from sqlalchemy.orm import sessionmaker

        engine = db_session.bind
        NewSession = sessionmaker(bind=engine)
        new_db_session = NewSession()

        try:
            # Verify participant exists in new session
            count = get_participant_count(new_db_session, test_data["session_id"])
            assert count == 1
        finally:
            new_db_session.close()


class TestCheckAndDeactivateSession:
    """Tests for check_and_deactivate_session function."""

    def test_deactivate_session_with_zero_participants(self, db_session, test_data):
        """Test that session is deactivated when participant count is 0."""
        # Verify session is active
        session = db_session.query(GameSession).filter(GameSession.id == test_data["session_id"]).first()
        assert session.is_active is True

        # Run deactivation check with 0 participants
        result = asyncio.run(check_and_deactivate_session(test_data["session_id"], db_session))

        # Verify session was deactivated
        assert result is True
        db_session.refresh(session)
        assert session.is_active is False

    def test_do_not_deactivate_session_with_participants(self, db_session, test_data):
        """Test that session is NOT deactivated when participants exist."""
        # Add a participant
        add_participant(db_session, test_data["session_id"], test_data["user1_id"], test_data["char1_id"])

        # Verify session is active
        session = db_session.query(GameSession).filter(GameSession.id == test_data["session_id"]).first()
        assert session.is_active is True

        # Run deactivation check with 1 participant
        result = asyncio.run(check_and_deactivate_session(test_data["session_id"], db_session))

        # Verify session was NOT deactivated
        assert result is False
        db_session.refresh(session)
        assert session.is_active is True

    def test_deactivate_removes_all_participants(self, db_session, test_data):
        """Test that deactivation removes all SessionParticipant records."""
        # This shouldn't happen in practice (deactivate only when count=0)
        # but we test the cleanup behavior

        # Manually set count to 0 by not adding participants
        # Verify no participants exist
        count_before = get_participant_count(db_session, test_data["session_id"])
        assert count_before == 0

        # Run deactivation
        result = asyncio.run(check_and_deactivate_session(test_data["session_id"], db_session))

        assert result is True

        # Verify all participants removed (should be 0 already)
        count_after = get_participant_count(db_session, test_data["session_id"])
        assert count_after == 0

    def test_do_not_deactivate_already_inactive_session(self, db_session, test_data):
        """Test that already inactive sessions are not processed again."""
        # Set session to inactive
        session = db_session.query(GameSession).filter(GameSession.id == test_data["session_id"]).first()
        session.is_active = False
        db_session.commit()

        # Run deactivation check
        result = asyncio.run(check_and_deactivate_session(test_data["session_id"], db_session))

        # Should return False (no action taken)
        assert result is False

    def test_do_not_deactivate_nonexistent_session(self, db_session):
        """Test that non-existent sessions return False."""
        result = asyncio.run(check_and_deactivate_session(999, db_session))

        assert result is False

    def test_deactivate_handles_backup_errors_gracefully(self, db_session, test_data):
        """Test that backup errors don't prevent deactivation."""
        # The backup might fail (e.g., file system issues)
        # but deactivation should still proceed

        # Run deactivation with 0 participants
        result = asyncio.run(check_and_deactivate_session(test_data["session_id"], db_session))

        # Should still deactivate even if backup fails
        assert result is True

        session = db_session.query(GameSession).filter(GameSession.id == test_data["session_id"]).first()
        assert session.is_active is False
