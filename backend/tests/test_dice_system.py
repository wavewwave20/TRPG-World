"""
Tests for the D20 dice system module.

Tests cover dice rolling, modifier calculation, ability score extraction,
status effect application, and outcome determination.
"""

from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Character, User
from app.schemas import JudgmentOutcome
from app.services.dice_system import ActionType, DiceSystem

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


def _make_character(db_session, user, data):
    """Helper to create a Character with the given data dict."""
    character = Character(
        user_id=user.id,
        name="Test Hero",
        data=data,
        created_at=datetime.utcnow(),
    )
    db_session.add(character)
    db_session.commit()
    db_session.refresh(character)
    return character


class TestRollD20:
    """Tests for DiceSystem.roll_d20."""

    def test_roll_in_range(self):
        """Roll result should be between 1 and 20."""
        for _ in range(100):
            result = DiceSystem.roll_d20()
            assert 1 <= result <= 20

    def test_roll_distribution(self):
        """All values 1-20 should appear over many rolls."""
        results = set()
        for _ in range(1000):
            results.add(DiceSystem.roll_d20())
        assert results == set(range(1, 21))


class TestCalculateAbilityModifier:
    """Tests for DiceSystem.calculate_ability_modifier."""

    @pytest.mark.parametrize(
        "score,expected",
        [
            (10, 0),   # Average
            (11, 0),   # Average (odd)
            (12, 1),
            (14, 2),
            (15, 2),   # Floor division
            (18, 4),
            (20, 5),
            (8, -1),
            (6, -2),
            (1, -5),   # Minimum
            (30, 10),  # Maximum
        ],
    )
    def test_modifier_values(self, score, expected):
        assert DiceSystem.calculate_ability_modifier(score) == expected


class TestGetAbilityScore:
    """Tests for DiceSystem.get_ability_score."""

    def test_get_strength(self, db_session, sample_user):
        character = _make_character(db_session, sample_user, {
            "strength": 18,
            "dexterity": 14,
            "constitution": 12,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        })
        assert DiceSystem.get_ability_score(character, ActionType.STRENGTH) == 18

    def test_get_dexterity(self, db_session, sample_user):
        character = _make_character(db_session, sample_user, {
            "strength": 10,
            "dexterity": 16,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        })
        assert DiceSystem.get_ability_score(character, ActionType.DEXTERITY) == 16

    def test_all_action_types(self, db_session, sample_user):
        scores = {
            "strength": 18,
            "dexterity": 16,
            "constitution": 14,
            "intelligence": 12,
            "wisdom": 10,
            "charisma": 8,
        }
        character = _make_character(db_session, sample_user, scores)

        for action_type in ActionType:
            expected = scores[action_type.value]
            assert DiceSystem.get_ability_score(character, action_type) == expected

    def test_missing_stat_defaults_to_10(self, db_session, sample_user):
        character = _make_character(db_session, sample_user, {})
        assert DiceSystem.get_ability_score(character, ActionType.STRENGTH) == 10


class TestApplyStatusEffects:
    """Tests for DiceSystem.apply_status_effects."""

    def test_no_effects(self, db_session, sample_user):
        character = _make_character(db_session, sample_user, {"status_effects": []})
        assert DiceSystem.apply_status_effects(3, character) == 3

    def test_positive_modifier(self, db_session, sample_user):
        character = _make_character(db_session, sample_user, {
            "status_effects": [{"name": "Blessed", "modifier": 2}],
        })
        assert DiceSystem.apply_status_effects(3, character) == 5

    def test_negative_modifier(self, db_session, sample_user):
        character = _make_character(db_session, sample_user, {
            "status_effects": [{"name": "Cursed", "modifier": -3}],
        })
        assert DiceSystem.apply_status_effects(3, character) == 0

    def test_multiple_effects(self, db_session, sample_user):
        character = _make_character(db_session, sample_user, {
            "status_effects": [
                {"name": "Blessed", "modifier": 2},
                {"name": "Weakened", "modifier": -1},
            ],
        })
        assert DiceSystem.apply_status_effects(3, character) == 4

    def test_string_effects_ignored(self, db_session, sample_user):
        """Legacy string effects should not affect modifier."""
        character = _make_character(db_session, sample_user, {
            "status_effects": ["Blessed", "Inspired"],
        })
        assert DiceSystem.apply_status_effects(3, character) == 3

    def test_dict_effects_without_modifier(self, db_session, sample_user):
        """Dict effects without modifier field should not affect result."""
        character = _make_character(db_session, sample_user, {
            "status_effects": [{"name": "Haste", "duration": 3}],
        })
        assert DiceSystem.apply_status_effects(3, character) == 3

    def test_no_status_effects_key(self, db_session, sample_user):
        """Missing status_effects key should not affect modifier."""
        character = _make_character(db_session, sample_user, {})
        assert DiceSystem.apply_status_effects(3, character) == 3


class TestCalculateModifier:
    """Tests for DiceSystem.calculate_modifier (full pipeline)."""

    def test_basic_modifier(self, db_session, sample_user):
        character = _make_character(db_session, sample_user, {
            "strength": 18,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
            "status_effects": [],
        })
        # STR 18 -> (18-10)//2 = 4
        assert DiceSystem.calculate_modifier(character, ActionType.STRENGTH) == 4

    def test_modifier_with_status_effects(self, db_session, sample_user):
        character = _make_character(db_session, sample_user, {
            "strength": 14,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
            "status_effects": [{"name": "Blessed", "modifier": 2}],
        })
        # STR 14 -> (14-10)//2 = 2, + blessed 2 = 4
        assert DiceSystem.calculate_modifier(character, ActionType.STRENGTH) == 4


class TestDetermineOutcome:
    """Tests for DiceSystem.determine_outcome."""

    def test_natural_1_always_critical_failure(self):
        """Natural 1 is always critical failure, regardless of modifier."""
        assert DiceSystem.determine_outcome(1, 100, 5) == JudgmentOutcome.CRITICAL_FAILURE

    def test_natural_20_always_critical_success(self):
        """Natural 20 is always critical success, regardless of DC."""
        assert DiceSystem.determine_outcome(20, -100, 30) == JudgmentOutcome.CRITICAL_SUCCESS

    def test_success_when_meets_dc(self):
        """Exactly meeting DC is a success."""
        assert DiceSystem.determine_outcome(10, 5, 15) == JudgmentOutcome.SUCCESS

    def test_success_when_exceeds_dc(self):
        """Exceeding DC is a success."""
        assert DiceSystem.determine_outcome(15, 5, 15) == JudgmentOutcome.SUCCESS

    def test_failure_when_below_dc(self):
        """Below DC is a failure."""
        assert DiceSystem.determine_outcome(5, 2, 15) == JudgmentOutcome.FAILURE

    def test_high_modifier_enables_success(self):
        """A high modifier can make a low roll succeed."""
        assert DiceSystem.determine_outcome(5, 10, 15) == JudgmentOutcome.SUCCESS

    def test_negative_modifier_causes_failure(self):
        """A negative modifier can make an otherwise good roll fail."""
        assert DiceSystem.determine_outcome(15, -5, 15) == JudgmentOutcome.FAILURE


class TestActionType:
    """Tests for ActionType enum."""

    def test_all_six_abilities(self):
        assert len(ActionType) == 6

    def test_values(self):
        assert ActionType.STRENGTH.value == "strength"
        assert ActionType.DEXTERITY.value == "dexterity"
        assert ActionType.CONSTITUTION.value == "constitution"
        assert ActionType.INTELLIGENCE.value == "intelligence"
        assert ActionType.WISDOM.value == "wisdom"
        assert ActionType.CHARISMA.value == "charisma"
