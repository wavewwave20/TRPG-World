"""
Tests for the ability score mapping fix in _character_to_sheet.

Verifies that character ability scores are correctly mapped
from both the new top-level format and legacy nested format.
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Character, User
from app.services.context_loader import _character_to_sheet

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
        name="Test Character",
        data=data,
        created_at=datetime.utcnow(),
    )
    db_session.add(character)
    db_session.commit()
    db_session.refresh(character)
    return character


class TestTopLevelAbilityScores:
    """Test the new top-level ability score format (from CharacterCreate)."""

    def test_all_scores_mapped_correctly(self, db_session, sample_user):
        character = _make_character(db_session, sample_user, {
            "strength": 18,
            "dexterity": 16,
            "constitution": 14,
            "intelligence": 12,
            "wisdom": 10,
            "charisma": 8,
        })
        sheet = _character_to_sheet(character)

        assert sheet.strength == 18
        assert sheet.dexterity == 16
        assert sheet.constitution == 14
        assert sheet.intelligence == 12
        assert sheet.wisdom == 10
        assert sheet.charisma == 8

    def test_modifier_calculation_from_top_level(self, db_session, sample_user):
        """Verify that a high stat actually produces non-zero modifier."""
        character = _make_character(db_session, sample_user, {
            "strength": 18,
            "dexterity": 14,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        })
        sheet = _character_to_sheet(character)

        # STR 18 -> modifier (18-10)//2 = +4
        assert (sheet.strength - 10) // 2 == 4
        # DEX 14 -> modifier (14-10)//2 = +2
        assert (sheet.dexterity - 10) // 2 == 2


class TestLegacyNestedAbilityScores:
    """Test the legacy nested ability_scores format."""

    def test_nested_format_still_works(self, db_session, sample_user):
        character = _make_character(db_session, sample_user, {
            "ability_scores": {
                "STR": 16,
                "DEX": 14,
                "CON": 15,
                "INT": 10,
                "WIS": 12,
                "CHA": 13,
            }
        })
        sheet = _character_to_sheet(character)

        assert sheet.strength == 16
        assert sheet.dexterity == 14
        assert sheet.constitution == 15
        assert sheet.intelligence == 10
        assert sheet.wisdom == 12
        assert sheet.charisma == 13


class TestMixedAndEdgeCases:
    """Test mixed formats and edge cases."""

    def test_top_level_takes_precedence_over_nested(self, db_session, sample_user):
        """If both formats exist, top-level should take precedence."""
        character = _make_character(db_session, sample_user, {
            "strength": 20,
            "dexterity": 18,
            "constitution": 16,
            "intelligence": 14,
            "wisdom": 12,
            "charisma": 10,
            "ability_scores": {
                "STR": 8,
                "DEX": 8,
                "CON": 8,
                "INT": 8,
                "WIS": 8,
                "CHA": 8,
            }
        })
        sheet = _character_to_sheet(character)

        assert sheet.strength == 20
        assert sheet.dexterity == 18
        assert sheet.constitution == 16
        assert sheet.intelligence == 14
        assert sheet.wisdom == 12
        assert sheet.charisma == 10

    def test_missing_scores_default_to_10(self, db_session, sample_user):
        """If no ability scores provided at all, default to 10."""
        character = _make_character(db_session, sample_user, {
            "age": 25,
            "race": "Human",
        })
        sheet = _character_to_sheet(character)

        assert sheet.strength == 10
        assert sheet.dexterity == 10
        assert sheet.constitution == 10
        assert sheet.intelligence == 10
        assert sheet.wisdom == 10
        assert sheet.charisma == 10

    def test_empty_data(self, db_session, sample_user):
        """Handle character with empty data dict."""
        character = _make_character(db_session, sample_user, {})
        sheet = _character_to_sheet(character)

        assert sheet.strength == 10
        assert sheet.name == "Test Character"

    def test_none_data(self, db_session, sample_user):
        """Handle character with None data."""
        character = _make_character(db_session, sample_user, None)
        sheet = _character_to_sheet(character)

        assert sheet.strength == 10

    def test_partial_top_level_fallback_to_nested(self, db_session, sample_user):
        """Some stats in top-level, missing ones fall back to nested."""
        character = _make_character(db_session, sample_user, {
            "strength": 18,
            "dexterity": 16,
            "ability_scores": {
                "CON": 14,
                "INT": 12,
                "WIS": 11,
                "CHA": 9,
            }
        })
        sheet = _character_to_sheet(character)

        assert sheet.strength == 18
        assert sheet.dexterity == 16
        assert sheet.constitution == 14
        assert sheet.intelligence == 12
        assert sheet.wisdom == 11
        assert sheet.charisma == 9


class TestSkillsAndEffects:
    """Test that skills and status effects are correctly extracted alongside ability fix."""

    def test_skills_as_list(self, db_session, sample_user):
        character = _make_character(db_session, sample_user, {
            "strength": 14,
            "dexterity": 14,
            "constitution": 14,
            "intelligence": 14,
            "wisdom": 14,
            "charisma": 14,
            "skills": [
                {"name": "Stealth", "type": "active", "description": "Hide in shadows"},
                {"name": "Perception", "type": "passive", "description": "Notice things"},
            ],
        })
        sheet = _character_to_sheet(character)

        assert len(sheet.skills) == 2
        assert sheet.skills[0]["name"] == "Stealth"

    def test_skills_as_dict(self, db_session, sample_user):
        character = _make_character(db_session, sample_user, {
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
            "skills": {"Athletics": 5, "Perception": 3},
        })
        sheet = _character_to_sheet(character)

        assert len(sheet.skills) == 2

    def test_status_effects_mixed_format(self, db_session, sample_user):
        character = _make_character(db_session, sample_user, {
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
            "status_effects": ["Blessed", {"name": "Haste", "duration": 3}],
        })
        sheet = _character_to_sheet(character)

        assert len(sheet.status_effects) == 2
        assert "Blessed" in sheet.status_effects
        assert "Haste" in sheet.status_effects
