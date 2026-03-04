"""
Tests for the character management API routes.

Tests cover CRUD operations, input validation, ability score storage,
skills/weaknesses persistence, and error handling for the
/api/characters endpoints.
"""

from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Character, CharacterShareCode, User
from app.routes.characters import router

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_engine():
    """Create a test database engine with all tables."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine):
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def app(db_engine):
    """Create a FastAPI test application with dependency overrides."""
    test_app = FastAPI()
    test_app.include_router(router)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


@pytest.fixture
def client(app):
    """Create a test HTTP client."""
    return TestClient(app)


@pytest.fixture
def sample_user(db_session):
    """Create a sample user in the test database."""
    user = User(username="testuser", password="hashed_password", created_at=datetime.utcnow())
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def second_user(db_session):
    """Create a second user in the test database."""
    user = User(username="seconduser", password="hashed_password2", created_at=datetime.utcnow())
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def valid_character_data(sample_user):
    """Return valid character creation payload."""
    return {
        "user_id": sample_user.id,
        "name": "Elf Archer",
        "age": 120,
        "race": "Elf",
        "concept": "Guardian of the forest",
        "strength": 12,
        "dexterity": 16,
        "constitution": 10,
        "intelligence": 14,
        "wisdom": 13,
        "charisma": 11,
        "skills": [
            {"type": "passive", "name": "Keen Sight", "description": "Can see far in the dark"},
            {"type": "active", "name": "Precision Shot", "description": "Focus and aim for a vital spot"},
        ],
        "weaknesses": ["Fear of darkness"],
    }


@pytest.fixture
def valid_update_data():
    """Return valid character update payload (no user_id needed)."""
    return {
        "name": "Updated Archer",
        "age": 121,
        "race": "High Elf",
        "concept": "Elder guardian",
        "strength": 14,
        "dexterity": 18,
        "constitution": 12,
        "intelligence": 15,
        "wisdom": 14,
        "charisma": 12,
        "skills": [
            {"type": "passive", "name": "Eagle Eye", "description": "Enhanced vision", "ability": "wisdom"},
        ],
        "weaknesses": ["Fear of fire", "Slow recovery"],
    }


def _create_character_via_db(db_session, user, name="Test Hero", data=None):
    """Helper to insert a Character directly in the database."""
    if data is None:
        data = {
            "age": 25,
            "race": "Human",
            "concept": "",
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
            "skills": [],
            "weaknesses": [],
            "status_effects": [],
            "inventory": [],
        }
    character = Character(
        user_id=user.id,
        name=name,
        data=data,
        created_at=datetime.utcnow(),
    )
    db_session.add(character)
    db_session.commit()
    db_session.refresh(character)
    return character


# ---------------------------------------------------------------------------
# CREATE (POST /api/characters/)
# ---------------------------------------------------------------------------


class TestCreateCharacter:
    """Tests for POST /api/characters/."""

    def test_create_character_success(self, client, valid_character_data):
        """Creating a character with valid data returns 201 and the character."""
        response = client.post("/api/characters/", json=valid_character_data)

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Elf Archer"
        assert body["user_id"] == valid_character_data["user_id"]
        assert "id" in body
        assert "created_at" in body

    def test_create_character_stores_ability_scores(self, client, valid_character_data):
        """Ability scores are persisted in the character data JSON."""
        response = client.post("/api/characters/", json=valid_character_data)

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["strength"] == 12
        assert data["dexterity"] == 16
        assert data["constitution"] == 10
        assert data["intelligence"] == 14
        assert data["wisdom"] == 13
        assert data["charisma"] == 11

    def test_create_character_stores_skills(self, client, valid_character_data):
        """Skills list is persisted in the character data JSON."""
        response = client.post("/api/characters/", json=valid_character_data)

        assert response.status_code == 201
        data = response.json()["data"]
        assert len(data["skills"]) == 2
        assert data["skills"][0]["name"] == "Keen Sight"
        assert data["skills"][1]["type"] == "active"

    def test_create_character_stores_skills_with_ability_field(self, client, sample_user):
        """Skills that include an 'ability' field are stored correctly."""
        payload = {
            "user_id": sample_user.id,
            "name": "Skilled Warrior",
            "age": 30,
            "race": "Human",
            "concept": "",
            "strength": 16,
            "dexterity": 12,
            "constitution": 14,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
            "skills": [
                {"type": "active", "name": "Power Attack", "description": "Heavy strike", "ability": "strength"},
                {"type": "passive", "name": "Quick Reflexes", "description": "Fast dodge", "ability": "dexterity"},
            ],
            "weaknesses": [],
        }

        response = client.post("/api/characters/", json=payload)

        assert response.status_code == 201
        skills = response.json()["data"]["skills"]
        assert skills[0]["ability"] == "strength"
        assert skills[1]["ability"] == "dexterity"

    def test_create_character_stores_weaknesses(self, client, valid_character_data):
        """Weaknesses list is persisted in the character data JSON."""
        response = client.post("/api/characters/", json=valid_character_data)

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["weaknesses"] == ["Fear of darkness"]

    def test_create_character_initializes_empty_status_effects(self, client, valid_character_data):
        """Newly created characters start with an empty status_effects list."""
        response = client.post("/api/characters/", json=valid_character_data)

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["status_effects"] == []

    def test_create_character_initializes_empty_inventory(self, client, valid_character_data):
        """Newly created characters start with an empty inventory list."""
        response = client.post("/api/characters/", json=valid_character_data)

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["inventory"] == []

    def test_create_character_stores_race_and_concept(self, client, valid_character_data):
        """Race and concept fields are persisted in character data."""
        response = client.post("/api/characters/", json=valid_character_data)

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["race"] == "Elf"
        assert data["concept"] == "Guardian of the forest"
        assert data["age"] == 120

    def test_create_character_with_defaults(self, client, sample_user):
        """Creating a character with only required fields uses defaults."""
        payload = {"user_id": sample_user.id, "name": "Minimal Hero"}

        response = client.post("/api/characters/", json=payload)

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["age"] == 25
        assert data["race"] == "\uc778\uac04"  # "인간" (Korean for "Human")
        assert data["concept"] == ""
        assert data["strength"] == 10
        assert data["dexterity"] == 10
        assert data["constitution"] == 10
        assert data["intelligence"] == 10
        assert data["wisdom"] == 10
        assert data["charisma"] == 10
        assert data["skills"] == []
        assert data["weaknesses"] == []

    def test_create_character_strips_name_whitespace(self, client, sample_user):
        """Leading and trailing whitespace in name is stripped."""
        payload = {"user_id": sample_user.id, "name": "  Trimmed Name  "}

        response = client.post("/api/characters/", json=payload)

        assert response.status_code == 201
        assert response.json()["name"] == "Trimmed Name"


class TestCreateCharacterValidation:
    """Validation tests for POST /api/characters/."""

    def test_missing_user_id(self, client):
        """Missing user_id returns 422 (unprocessable entity)."""
        payload = {"name": "No User"}

        response = client.post("/api/characters/", json=payload)

        assert response.status_code == 422

    def test_missing_name(self, client, sample_user):
        """Missing name returns 422 (unprocessable entity)."""
        payload = {"user_id": sample_user.id}

        response = client.post("/api/characters/", json=payload)

        assert response.status_code == 422

    def test_empty_name_string(self, client, sample_user):
        """Empty string name is rejected by Pydantic min_length=1."""
        payload = {"user_id": sample_user.id, "name": ""}

        response = client.post("/api/characters/", json=payload)

        assert response.status_code == 422

    def test_nonexistent_user_id(self, client):
        """Referencing a user that does not exist returns 404."""
        payload = {"user_id": 99999, "name": "Orphan Character"}

        response = client.post("/api/characters/", json=payload)

        assert response.status_code == 404
        assert "User" in response.json()["detail"]

    def test_ability_score_below_minimum(self, client, sample_user):
        """Ability score below 1 is rejected."""
        payload = {
            "user_id": sample_user.id,
            "name": "Weak Hero",
            "strength": 0,
        }

        response = client.post("/api/characters/", json=payload)

        assert response.status_code == 422

    def test_ability_score_above_maximum(self, client, sample_user):
        """Ability score above 30 is rejected."""
        payload = {
            "user_id": sample_user.id,
            "name": "Overpowered Hero",
            "strength": 31,
        }

        response = client.post("/api/characters/", json=payload)

        assert response.status_code == 422

    def test_ability_score_at_minimum_boundary(self, client, sample_user):
        """Ability score exactly 1 is accepted."""
        payload = {
            "user_id": sample_user.id,
            "name": "Weakest Hero",
            "strength": 1,
            "dexterity": 1,
            "constitution": 1,
            "intelligence": 1,
            "wisdom": 1,
            "charisma": 1,
        }

        response = client.post("/api/characters/", json=payload)

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["strength"] == 1

    def test_ability_score_at_maximum_boundary(self, client, sample_user):
        """Ability score exactly 30 is accepted."""
        payload = {
            "user_id": sample_user.id,
            "name": "Strongest Hero",
            "strength": 30,
            "dexterity": 30,
            "constitution": 30,
            "intelligence": 30,
            "wisdom": 30,
            "charisma": 30,
        }

        response = client.post("/api/characters/", json=payload)

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["strength"] == 30
        assert data["charisma"] == 30

    def test_negative_age_rejected(self, client, sample_user):
        """Age below 1 is rejected (ge=1)."""
        payload = {"user_id": sample_user.id, "name": "Unborn", "age": 0}

        response = client.post("/api/characters/", json=payload)

        assert response.status_code == 422

    def test_each_ability_score_validated_independently(self, client, sample_user):
        """Each of the six ability scores enforces the 1-30 range."""
        abilities = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
        for ability in abilities:
            payload = {"user_id": sample_user.id, "name": f"Bad {ability}"}
            payload[ability] = 31

            response = client.post("/api/characters/", json=payload)

            assert response.status_code == 422, f"{ability}=31 should be rejected"

    def test_empty_request_body(self, client):
        """Sending an empty JSON body returns 422."""
        response = client.post("/api/characters/", json={})

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# READ (GET /api/characters/{character_id})
# ---------------------------------------------------------------------------


class TestGetCharacter:
    """Tests for GET /api/characters/{character_id}."""

    def test_get_existing_character(self, client, db_session, sample_user):
        """Retrieving an existing character returns 200 and correct data."""
        char = _create_character_via_db(db_session, sample_user, name="Findable Hero")

        response = client.get(f"/api/characters/{char.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == char.id
        assert body["name"] == "Findable Hero"
        assert body["user_id"] == sample_user.id

    def test_get_character_returns_data_blob(self, client, db_session, sample_user):
        """The data JSON blob is included in the response."""
        data = {
            "age": 30,
            "race": "Dwarf",
            "concept": "Miner",
            "strength": 18,
            "dexterity": 8,
            "constitution": 16,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 6,
            "skills": [{"name": "Mining", "type": "passive", "description": "Expert miner"}],
            "weaknesses": ["Claustrophobia"],
            "status_effects": [{"name": "Blessed", "modifier": 2}],
            "inventory": ["Pickaxe"],
        }
        char = _create_character_via_db(db_session, sample_user, name="Dwarf Miner", data=data)

        response = client.get(f"/api/characters/{char.id}")

        assert response.status_code == 200
        returned_data = response.json()["data"]
        assert returned_data["strength"] == 18
        assert returned_data["race"] == "Dwarf"
        assert returned_data["skills"][0]["name"] == "Mining"
        assert returned_data["status_effects"][0]["modifier"] == 2
        assert returned_data["inventory"] == ["Pickaxe"]

    def test_get_character_includes_created_at(self, client, db_session, sample_user):
        """The response includes a created_at ISO-format timestamp."""
        char = _create_character_via_db(db_session, sample_user)

        response = client.get(f"/api/characters/{char.id}")

        assert response.status_code == 200
        created_at = response.json()["created_at"]
        # Should be a valid ISO format string
        datetime.fromisoformat(created_at)

    def test_get_nonexistent_character(self, client):
        """Requesting a character that does not exist returns 404."""
        response = client.get("/api/characters/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


# ---------------------------------------------------------------------------
# READ (GET /api/characters/user/{user_id})
# ---------------------------------------------------------------------------


class TestGetUserCharacters:
    """Tests for GET /api/characters/user/{user_id}."""

    def test_get_characters_for_user_with_multiple(self, client, db_session, sample_user):
        """Returns all characters belonging to a user."""
        _create_character_via_db(db_session, sample_user, name="Hero A")
        _create_character_via_db(db_session, sample_user, name="Hero B")
        _create_character_via_db(db_session, sample_user, name="Hero C")

        response = client.get(f"/api/characters/user/{sample_user.id}")

        assert response.status_code == 200
        characters = response.json()
        assert len(characters) == 3
        names = {c["name"] for c in characters}
        assert names == {"Hero A", "Hero B", "Hero C"}

    def test_get_characters_for_user_with_none(self, client, sample_user):
        """Returns an empty list when the user has no characters."""
        response = client.get(f"/api/characters/user/{sample_user.id}")

        assert response.status_code == 200
        assert response.json() == []

    def test_get_characters_only_returns_own(self, client, db_session, sample_user, second_user):
        """Characters from other users are not included."""
        _create_character_via_db(db_session, sample_user, name="User1 Hero")
        _create_character_via_db(db_session, second_user, name="User2 Hero")

        response = client.get(f"/api/characters/user/{sample_user.id}")

        assert response.status_code == 200
        characters = response.json()
        assert len(characters) == 1
        assert characters[0]["name"] == "User1 Hero"

    def test_get_characters_for_nonexistent_user(self, client):
        """Returns an empty list for a user ID that does not exist."""
        response = client.get("/api/characters/user/99999")

        assert response.status_code == 200
        assert response.json() == []

    def test_each_character_has_expected_fields(self, client, db_session, sample_user):
        """Each item in the list has the expected response fields."""
        _create_character_via_db(db_session, sample_user, name="Field Check Hero")

        response = client.get(f"/api/characters/user/{sample_user.id}")

        assert response.status_code == 200
        char = response.json()[0]
        assert "id" in char
        assert "user_id" in char
        assert "name" in char
        assert "data" in char
        assert "created_at" in char


# ---------------------------------------------------------------------------
# UPDATE (PUT /api/characters/{character_id})
# ---------------------------------------------------------------------------


class TestUpdateCharacter:
    """Tests for PUT /api/characters/{character_id}."""

    def test_update_character_success(self, client, db_session, sample_user, valid_update_data):
        """Updating an existing character returns 200 and the updated data."""
        char = _create_character_via_db(db_session, sample_user, name="Old Name")

        response = client.put(f"/api/characters/{char.id}", json=valid_update_data)

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Updated Archer"
        assert body["data"]["race"] == "High Elf"
        assert body["data"]["strength"] == 14
        assert body["data"]["dexterity"] == 18

    def test_update_character_changes_ability_scores(self, client, db_session, sample_user):
        """Ability scores are updated correctly."""
        char = _create_character_via_db(db_session, sample_user)
        update = {
            "name": "Buffed Hero",
            "age": 26,
            "race": "Human",
            "strength": 20,
            "dexterity": 18,
            "constitution": 16,
            "intelligence": 14,
            "wisdom": 12,
            "charisma": 10,
        }

        response = client.put(f"/api/characters/{char.id}", json=update)

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["strength"] == 20
        assert data["dexterity"] == 18
        assert data["constitution"] == 16

    def test_update_character_preserves_status_effects(self, client, db_session, sample_user):
        """Existing status_effects are preserved across updates."""
        original_data = {
            "age": 25,
            "race": "Human",
            "concept": "",
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
            "skills": [],
            "weaknesses": [],
            "status_effects": [{"name": "Blessed", "modifier": 2}],
            "inventory": ["Sword"],
        }
        char = _create_character_via_db(db_session, sample_user, data=original_data)

        update = {
            "name": "Still Blessed",
            "age": 25,
            "race": "Human",
            "strength": 12,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        }

        response = client.put(f"/api/characters/{char.id}", json=update)

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status_effects"] == [{"name": "Blessed", "modifier": 2}]

    def test_update_character_preserves_inventory(self, client, db_session, sample_user):
        """Existing inventory is preserved across updates."""
        original_data = {
            "age": 25,
            "race": "Human",
            "concept": "",
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
            "skills": [],
            "weaknesses": [],
            "status_effects": [],
            "inventory": ["Sword", "Shield"],
        }
        char = _create_character_via_db(db_session, sample_user, data=original_data)

        update = {
            "name": "Equipped Hero",
            "age": 25,
            "race": "Human",
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        }

        response = client.put(f"/api/characters/{char.id}", json=update)

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["inventory"] == ["Sword", "Shield"]

    def test_update_replaces_skills(self, client, db_session, sample_user, valid_update_data):
        """Skills list is fully replaced on update."""
        original_data = {
            "age": 25,
            "race": "Human",
            "concept": "",
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
            "skills": [{"type": "passive", "name": "Old Skill", "description": "Obsolete"}],
            "weaknesses": ["Old weakness"],
            "status_effects": [],
            "inventory": [],
        }
        char = _create_character_via_db(db_session, sample_user, data=original_data)

        response = client.put(f"/api/characters/{char.id}", json=valid_update_data)

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["skills"]) == 1
        assert data["skills"][0]["name"] == "Eagle Eye"
        assert data["skills"][0]["ability"] == "wisdom"

    def test_update_replaces_weaknesses(self, client, db_session, sample_user, valid_update_data):
        """Weaknesses list is fully replaced on update."""
        char = _create_character_via_db(db_session, sample_user)

        response = client.put(f"/api/characters/{char.id}", json=valid_update_data)

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["weaknesses"] == ["Fear of fire", "Slow recovery"]

    def test_update_nonexistent_character(self, client, valid_update_data):
        """Updating a character that does not exist returns 404."""
        response = client.put("/api/characters/99999", json=valid_update_data)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_update_strips_name_whitespace(self, client, db_session, sample_user):
        """Leading and trailing whitespace in name is stripped on update."""
        char = _create_character_via_db(db_session, sample_user)
        update = {
            "name": "  Trimmed  ",
            "age": 25,
            "race": "Human",
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        }

        response = client.put(f"/api/characters/{char.id}", json=update)

        assert response.status_code == 200
        assert response.json()["name"] == "Trimmed"


class TestUpdateCharacterValidation:
    """Validation tests for PUT /api/characters/{character_id}."""

    def test_update_missing_name(self, client, db_session, sample_user):
        """Omitting name from the update payload returns 422."""
        char = _create_character_via_db(db_session, sample_user)
        update = {
            "age": 25,
            "race": "Human",
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        }

        response = client.put(f"/api/characters/{char.id}", json=update)

        assert response.status_code == 422

    def test_update_empty_name(self, client, db_session, sample_user):
        """Empty string name is rejected by Pydantic min_length=1."""
        char = _create_character_via_db(db_session, sample_user)
        update = {
            "name": "",
            "age": 25,
            "race": "Human",
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        }

        response = client.put(f"/api/characters/{char.id}", json=update)

        assert response.status_code == 422

    def test_update_ability_score_out_of_range(self, client, db_session, sample_user):
        """Ability score outside 1-30 is rejected on update."""
        char = _create_character_via_db(db_session, sample_user)
        update = {
            "name": "Invalid",
            "age": 25,
            "race": "Human",
            "strength": 50,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        }

        response = client.put(f"/api/characters/{char.id}", json=update)

        assert response.status_code == 422

    def test_update_ability_score_below_minimum(self, client, db_session, sample_user):
        """Ability score below 1 is rejected on update."""
        char = _create_character_via_db(db_session, sample_user)
        update = {
            "name": "Too Weak",
            "age": 25,
            "race": "Human",
            "strength": 0,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        }

        response = client.put(f"/api/characters/{char.id}", json=update)

        assert response.status_code == 422

    def test_update_missing_required_ability_scores(self, client, db_session, sample_user):
        """Omitting required ability scores returns 422 (all are required in CharacterUpdate)."""
        char = _create_character_via_db(db_session, sample_user)
        update = {
            "name": "Incomplete",
            "age": 25,
            "race": "Human",
            # All ability scores omitted
        }

        response = client.put(f"/api/characters/{char.id}", json=update)

        assert response.status_code == 422

    def test_update_empty_body(self, client, db_session, sample_user):
        """Sending an empty body returns 422."""
        char = _create_character_via_db(db_session, sample_user)

        response = client.put(f"/api/characters/{char.id}", json={})

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# DUPLICATE (POST /api/characters/{character_id}/duplicate)
# ---------------------------------------------------------------------------


class TestDuplicateCharacter:
    """Tests for POST /api/characters/{character_id}/duplicate."""

    def test_duplicate_character_success(self, client, db_session, sample_user):
        """Duplicating an existing character returns 201 and copied data."""
        original_data = {
            "age": 33,
            "race": "Elf",
            "concept": "Scout",
            "strength": 12,
            "dexterity": 17,
            "constitution": 11,
            "intelligence": 13,
            "wisdom": 14,
            "charisma": 9,
            "skills": [{"type": "active", "name": "Rapid Shot", "description": "Two quick arrows"}],
            "weaknesses": ["Pride"],
            "status_effects": [{"name": "Blessed", "modifier": 2}],
            "inventory": ["Bow", "Cloak"],
        }
        original = _create_character_via_db(db_session, sample_user, name="Ranger", data=original_data)

        response = client.post(f"/api/characters/{original.id}/duplicate")

        assert response.status_code == 201
        body = response.json()
        assert body["id"] != original.id
        assert body["user_id"] == original.user_id
        assert body["name"] == "Ranger (복제본)"
        assert body["data"]["inventory"] == original_data["inventory"]
        assert body["data"]["skills"] == original_data["skills"]
        assert body["data"]["status_effects"] == original_data["status_effects"]
        assert any(status["name"] == "Pride" for status in body["data"]["statuses"])

    def test_duplicate_character_not_found(self, client):
        """Duplicating a non-existent character returns 404."""
        response = client.post("/api/characters/99999/duplicate")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_duplicate_character_uses_incremented_name_if_needed(self, client, db_session, sample_user):
        """Duplicate name gets a numeric suffix when base duplicate name already exists."""
        original = _create_character_via_db(db_session, sample_user, name="Mage")
        _create_character_via_db(db_session, sample_user, name="Mage (복제본)")

        response = client.post(f"/api/characters/{original.id}/duplicate")

        assert response.status_code == 201
        assert response.json()["name"] == "Mage (복제본 2)"


# ---------------------------------------------------------------------------
# SHARE CODE (POST /api/characters/{character_id}/share-code, /api/characters/share/redeem)
# ---------------------------------------------------------------------------


class TestCharacterShareCode:
    """Tests for character share code creation and redemption."""

    def test_create_share_code_success(self, client, db_session, sample_user):
        """Owner can create a 9-digit share code."""
        char = _create_character_via_db(db_session, sample_user, name="Sharable Hero")

        response = client.post(f"/api/characters/{char.id}/share-code", json={"user_id": sample_user.id})

        assert response.status_code == 201
        body = response.json()
        assert body["character_id"] == char.id
        assert body["character_name"] == "Sharable Hero"
        assert len(body["share_code"]) == 9
        assert body["share_code"].isdigit()

    def test_create_share_code_requires_owner(self, client, db_session, sample_user, second_user):
        """Non-owner cannot create share code for someone else's character."""
        char = _create_character_via_db(db_session, sample_user, name="Private Hero")

        response = client.post(f"/api/characters/{char.id}/share-code", json={"user_id": second_user.id})

        assert response.status_code == 403

    def test_redeem_share_code_success(self, client, db_session, sample_user, second_user):
        """Recipient can redeem share code and receives a cloned character."""
        source_data = {
            "age": 27,
            "race": "Human",
            "concept": "Swordsman",
            "strength": 15,
            "dexterity": 12,
            "constitution": 13,
            "intelligence": 9,
            "wisdom": 10,
            "charisma": 11,
            "skills": [{"type": "active", "name": "Slash", "description": "Basic slash"}],
            "weaknesses": ["Impatient"],
            "status_effects": [],
            "inventory": ["Sword"],
        }
        source_char = _create_character_via_db(db_session, sample_user, name="Source Hero", data=source_data)

        create_resp = client.post(
            f"/api/characters/{source_char.id}/share-code",
            json={"user_id": sample_user.id},
        )
        share_code = create_resp.json()["share_code"]

        redeem_resp = client.post(
            "/api/characters/share/redeem",
            json={"user_id": second_user.id, "share_code": share_code},
        )

        assert redeem_resp.status_code == 201
        redeemed = redeem_resp.json()["character"]
        assert redeemed["user_id"] == second_user.id
        assert redeemed["name"] == "Source Hero"
        assert redeemed["data"]["inventory"] == source_data["inventory"]
        assert redeemed["data"]["skills"] == source_data["skills"]
        assert redeemed["data"]["status_effects"] == source_data["status_effects"]
        assert any(status["name"] == "Impatient" for status in redeemed["data"]["statuses"])
        assert redeemed["id"] != source_char.id

    def test_redeem_share_code_cannot_be_used_twice(self, client, db_session, sample_user, second_user):
        """Share codes are one-time and cannot be redeemed again."""
        source_char = _create_character_via_db(db_session, sample_user, name="One Time Hero")

        create_resp = client.post(
            f"/api/characters/{source_char.id}/share-code",
            json={"user_id": sample_user.id},
        )
        share_code = create_resp.json()["share_code"]

        first_redeem = client.post(
            "/api/characters/share/redeem",
            json={"user_id": second_user.id, "share_code": share_code},
        )
        assert first_redeem.status_code == 201

        second_redeem = client.post(
            "/api/characters/share/redeem",
            json={"user_id": second_user.id, "share_code": share_code},
        )
        assert second_redeem.status_code == 400
        assert "already been used" in second_redeem.json()["detail"]

    def test_redeem_share_code_expired(self, client, db_session, sample_user, second_user):
        """Share code expires after 3 minutes and cannot be redeemed."""
        source_char = _create_character_via_db(db_session, sample_user, name="Expired Hero")
        create_resp = client.post(
            f"/api/characters/{source_char.id}/share-code",
            json={"user_id": sample_user.id},
        )
        share_code = create_resp.json()["share_code"]

        share_entry = db_session.query(CharacterShareCode).filter(CharacterShareCode.code == share_code).first()
        assert share_entry is not None
        share_entry.created_at = datetime.utcnow() - timedelta(minutes=4)
        db_session.commit()

        response = client.post(
            "/api/characters/share/redeem",
            json={"user_id": second_user.id, "share_code": share_code},
        )

        assert response.status_code == 400
        assert "expired" in response.json()["detail"]

    def test_redeem_share_code_rejects_invalid_format(self, client, sample_user):
        """Share code must be exactly a 9-digit number."""
        response = client.post(
            "/api/characters/share/redeem",
            json={"user_id": sample_user.id, "share_code": "12ab"},
        )

        assert response.status_code == 400
        assert "9-digit" in response.json()["detail"]

    def test_redeem_share_code_rejects_self_redeem(self, client, db_session, sample_user):
        """Owner cannot redeem their own share code."""
        source_char = _create_character_via_db(db_session, sample_user, name="Self Hero")
        create_resp = client.post(
            f"/api/characters/{source_char.id}/share-code",
            json={"user_id": sample_user.id},
        )
        share_code = create_resp.json()["share_code"]

        response = client.post(
            "/api/characters/share/redeem",
            json={"user_id": sample_user.id, "share_code": share_code},
        )

        assert response.status_code == 400
        assert "cannot redeem your own" in response.json()["detail"]

    def test_redeem_share_code_resolves_name_collision(self, client, db_session, sample_user, second_user):
        """If recipient already has same name, shared copy gets '(공유본)' suffix."""
        source_char = _create_character_via_db(db_session, sample_user, name="Duplicate Name")
        _create_character_via_db(db_session, second_user, name="Duplicate Name")

        create_resp = client.post(
            f"/api/characters/{source_char.id}/share-code",
            json={"user_id": sample_user.id},
        )
        share_code = create_resp.json()["share_code"]

        response = client.post(
            "/api/characters/share/redeem",
            json={"user_id": second_user.id, "share_code": share_code},
        )

        assert response.status_code == 201
        assert response.json()["character"]["name"] == "Duplicate Name (공유본)"


# ---------------------------------------------------------------------------
# DELETE (DELETE /api/characters/{character_id})
# ---------------------------------------------------------------------------


class TestDeleteCharacter:
    """Tests for DELETE /api/characters/{character_id}."""

    def test_delete_character_success(self, client, db_session, sample_user):
        """Deleting an existing character returns 204 with no content."""
        char = _create_character_via_db(db_session, sample_user, name="Doomed Hero")

        response = client.delete(f"/api/characters/{char.id}")

        assert response.status_code == 204

    def test_delete_character_is_gone(self, client, db_session, sample_user):
        """After deletion, the character can no longer be retrieved."""
        char = _create_character_via_db(db_session, sample_user, name="Soon Gone")
        char_id = char.id

        client.delete(f"/api/characters/{char_id}")

        get_response = client.get(f"/api/characters/{char_id}")
        assert get_response.status_code == 404

    def test_delete_nonexistent_character(self, client):
        """Deleting a character that does not exist returns 404."""
        response = client.delete("/api/characters/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_delete_does_not_affect_other_characters(self, client, db_session, sample_user):
        """Deleting one character does not remove other characters."""
        char_a = _create_character_via_db(db_session, sample_user, name="Survivor")
        char_b = _create_character_via_db(db_session, sample_user, name="Deleted")

        client.delete(f"/api/characters/{char_b.id}")

        response = client.get(f"/api/characters/{char_a.id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Survivor"

    def test_delete_idempotency(self, client, db_session, sample_user):
        """Deleting the same character twice returns 404 on the second attempt."""
        char = _create_character_via_db(db_session, sample_user)
        char_id = char.id

        first_response = client.delete(f"/api/characters/{char_id}")
        assert first_response.status_code == 204

        second_response = client.delete(f"/api/characters/{char_id}")
        assert second_response.status_code == 404


# ---------------------------------------------------------------------------
# STATUS EFFECTS STORAGE
# ---------------------------------------------------------------------------


class TestStatusEffectsStorage:
    """Tests for status effects being stored and preserved correctly."""

    def test_status_effects_stored_via_direct_db_insert(self, client, db_session, sample_user):
        """Status effects in the data blob are returned via the GET endpoint."""
        data = {
            "age": 25,
            "race": "Human",
            "concept": "",
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
            "skills": [],
            "weaknesses": [],
            "status_effects": [
                {"name": "Blessed", "modifier": 2},
                {"name": "Poisoned", "modifier": -1},
            ],
            "inventory": [],
        }
        char = _create_character_via_db(db_session, sample_user, data=data)

        response = client.get(f"/api/characters/{char.id}")

        assert response.status_code == 200
        effects = response.json()["data"]["status_effects"]
        assert len(effects) == 2
        assert effects[0]["name"] == "Blessed"
        assert effects[0]["modifier"] == 2
        assert effects[1]["name"] == "Poisoned"
        assert effects[1]["modifier"] == -1

    def test_update_preserves_status_effects_when_not_in_data(self, client, db_session, sample_user):
        """Status effects survive an update that does not include them."""
        data = {
            "age": 25,
            "race": "Human",
            "concept": "",
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
            "skills": [],
            "weaknesses": [],
            "status_effects": [{"name": "Haste", "modifier": 3}],
            "inventory": [],
        }
        char = _create_character_via_db(db_session, sample_user, data=data)

        update = {
            "name": "Still Hasted",
            "age": 25,
            "race": "Human",
            "strength": 12,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        }

        response = client.put(f"/api/characters/{char.id}", json=update)

        assert response.status_code == 200
        effects = response.json()["data"]["status_effects"]
        assert len(effects) == 1
        assert effects[0]["name"] == "Haste"
        assert effects[0]["modifier"] == 3

    def test_no_status_effects_key_defaults_to_empty_on_update(self, client, db_session, sample_user):
        """If original data lacks status_effects, update sets it to empty list."""
        data = {
            "age": 25,
            "race": "Human",
            "concept": "",
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
            "skills": [],
            "weaknesses": [],
            # No status_effects key
            "inventory": [],
        }
        char = _create_character_via_db(db_session, sample_user, data=data)

        update = {
            "name": "No Effects",
            "age": 25,
            "race": "Human",
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        }

        response = client.put(f"/api/characters/{char.id}", json=update)

        assert response.status_code == 200
        effects = response.json()["data"]["status_effects"]
        assert effects == []


# ---------------------------------------------------------------------------
# FULL CRUD LIFECYCLE
# ---------------------------------------------------------------------------


class TestCharacterLifecycle:
    """End-to-end tests exercising the full create-read-update-delete flow."""

    def test_full_lifecycle(self, client, sample_user):
        """Create, read, update, and delete a character in sequence."""
        # CREATE
        create_payload = {
            "user_id": sample_user.id,
            "name": "Lifecycle Hero",
            "age": 25,
            "race": "Human",
            "concept": "Test subject",
            "strength": 14,
            "dexterity": 12,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
            "skills": [{"type": "active", "name": "Slash", "description": "Basic attack"}],
            "weaknesses": ["Fear of spiders"],
        }
        create_resp = client.post("/api/characters/", json=create_payload)
        assert create_resp.status_code == 201
        char_id = create_resp.json()["id"]

        # READ
        get_resp = client.get(f"/api/characters/{char_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Lifecycle Hero"
        assert get_resp.json()["data"]["strength"] == 14
        assert get_resp.json()["data"]["skills"][0]["name"] == "Slash"

        # UPDATE
        update_payload = {
            "name": "Evolved Hero",
            "age": 26,
            "race": "Human",
            "concept": "Battle-tested",
            "strength": 16,
            "dexterity": 14,
            "constitution": 12,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
            "skills": [
                {"type": "active", "name": "Power Slash", "description": "Enhanced attack"},
            ],
            "weaknesses": [],
        }
        update_resp = client.put(f"/api/characters/{char_id}", json=update_payload)
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "Evolved Hero"
        assert update_resp.json()["data"]["strength"] == 16

        # Verify update persisted
        verify_resp = client.get(f"/api/characters/{char_id}")
        assert verify_resp.json()["name"] == "Evolved Hero"
        assert verify_resp.json()["data"]["skills"][0]["name"] == "Power Slash"
        assert verify_resp.json()["data"]["weaknesses"] == []

        # DELETE
        del_resp = client.delete(f"/api/characters/{char_id}")
        assert del_resp.status_code == 204

        # Verify deletion
        gone_resp = client.get(f"/api/characters/{char_id}")
        assert gone_resp.status_code == 404

    def test_create_multiple_and_list(self, client, sample_user):
        """Creating several characters and listing them returns all of them."""
        names = ["Alpha", "Beta", "Gamma"]
        for name in names:
            payload = {"user_id": sample_user.id, "name": name}
            resp = client.post("/api/characters/", json=payload)
            assert resp.status_code == 201

        list_resp = client.get(f"/api/characters/user/{sample_user.id}")
        assert list_resp.status_code == 200
        returned_names = {c["name"] for c in list_resp.json()}
        assert returned_names == set(names)
