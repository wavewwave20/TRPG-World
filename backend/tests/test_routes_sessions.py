"""Tests for session API routes."""

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Character, GameSession, SessionActivityLog, SessionParticipant, User
from app.routes.sessions import router

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_engine():
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
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def app(db_engine):
    test_app = FastAPI()
    test_app.include_router(router)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


def _create_user(db_session, username: str) -> User:
    user = User(username=username, password="hashed_password", created_at=datetime.utcnow())
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_character(db_session, user: User, name: str) -> Character:
    character = Character(
        user_id=user.id,
        name=name,
        data={
            "age": 20,
            "race": "Human",
            "concept": "Adventurer",
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
        },
        created_at=datetime.utcnow(),
    )
    db_session.add(character)
    db_session.commit()
    db_session.refresh(character)
    return character


def _create_session(db_session, host_user_id: int, is_active: bool = True) -> GameSession:
    session = GameSession(
        host_user_id=host_user_id,
        title="Test Session",
        world_prompt="Test world prompt",
        is_active=is_active,
        created_at=datetime.utcnow(),
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


def test_create_session_applies_story_pacing_defaults(client, db_session):
    host = _create_user(db_session, "session_create_default_host")

    response = client.post(
        "/api/sessions/",
        json={
            "host_user_id": host.id,
            "title": "Default Story Session",
            "world_prompt": "Default world prompt",
        },
    )

    assert response.status_code == 201
    session_id = response.json()["session_id"]

    created = db_session.query(GameSession).filter(GameSession.id == session_id).first()
    assert created is not None
    assert created.max_acts == 4
    assert created.act_min_narrative_turns == 5


def test_create_session_supports_unlimited_story_pacing(client, db_session):
    host = _create_user(db_session, "session_create_unlimited_host")

    response = client.post(
        "/api/sessions/",
        json={
            "host_user_id": host.id,
            "title": "Unlimited Story Session",
            "world_prompt": "Unlimited world prompt",
            "max_acts": None,
            "act_min_narrative_turns": None,
        },
    )

    assert response.status_code == 201
    session_id = response.json()["session_id"]

    created = db_session.query(GameSession).filter(GameSession.id == session_id).first()
    assert created is not None
    assert created.max_acts is None
    assert created.act_min_narrative_turns is None


@pytest.mark.parametrize(
    "payload,expected_detail",
    [
        (
            {
                "title": "Invalid Max Acts",
                "world_prompt": "prompt",
                "max_acts": 1,
                "act_min_narrative_turns": 5,
            },
            "max_acts must be >= 2 or null",
        ),
        (
            {
                "title": "Invalid Min Turns",
                "world_prompt": "prompt",
                "max_acts": 4,
                "act_min_narrative_turns": 2,
            },
            "act_min_narrative_turns must be >= 3 or null",
        ),
    ],
)
def test_create_session_rejects_invalid_story_pacing_values(client, db_session, payload, expected_detail):
    host = _create_user(db_session, f"session_create_invalid_host_{payload['title'].replace(' ', '_').lower()}")

    response = client.post(
        "/api/sessions/",
        json={
            "host_user_id": host.id,
            **payload,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == expected_detail


def test_join_session_creates_participant(client, db_session):
    user = _create_user(db_session, "session_join_user")
    character = _create_character(db_session, user, "First Hero")
    session = _create_session(db_session, host_user_id=user.id, is_active=True)

    response = client.post(
        f"/api/sessions/{session.id}/join",
        json={"user_id": user.id, "character_id": character.id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rejoined"] is False
    assert body["character_name"] == "First Hero"

    participants = (
        db_session.query(SessionParticipant)
        .filter(SessionParticipant.session_id == session.id, SessionParticipant.user_id == user.id)
        .all()
    )
    assert len(participants) == 1
    assert participants[0].character_id == character.id


def test_join_session_is_idempotent_and_updates_character(client, db_session):
    user = _create_user(db_session, "session_rejoin_user")
    first_character = _create_character(db_session, user, "First Hero")
    second_character = _create_character(db_session, user, "Second Hero")
    session = _create_session(db_session, host_user_id=user.id, is_active=True)

    db_session.add(
        SessionParticipant(
            session_id=session.id,
            user_id=user.id,
            character_id=first_character.id,
            joined_at=datetime.utcnow(),
        )
    )
    db_session.commit()

    response = client.post(
        f"/api/sessions/{session.id}/join",
        json={"user_id": user.id, "character_id": second_character.id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rejoined"] is True
    assert body["character_name"] == "Second Hero"

    participants = (
        db_session.query(SessionParticipant)
        .filter(SessionParticipant.session_id == session.id, SessionParticipant.user_id == user.id)
        .all()
    )
    assert len(participants) == 1
    assert participants[0].character_id == second_character.id


def test_join_session_rejects_inactive_session(client, db_session):
    user = _create_user(db_session, "inactive_session_user")
    character = _create_character(db_session, user, "Inactive Hero")
    session = _create_session(db_session, host_user_id=user.id, is_active=False)

    response = client.post(
        f"/api/sessions/{session.id}/join",
        json={"user_id": user.id, "character_id": character.id},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "세션이 종료되었습니다."


def test_restart_session_writes_activity_log_and_can_be_listed(client, db_session):
    host = _create_user(db_session, "host_for_restart_log")
    session = _create_session(db_session, host_user_id=host.id, is_active=False)

    restart_response = client.post(f"/api/sessions/{session.id}/restart?user_id={host.id}")
    assert restart_response.status_code == 200

    log_row = (
        db_session.query(SessionActivityLog)
        .filter(
            SessionActivityLog.session_id == session.id,
            SessionActivityLog.action_type == "session.restart",
        )
        .order_by(SessionActivityLog.id.desc())
        .first()
    )
    assert log_row is not None
    assert log_row.status == "success"

    list_response = client.get(f"/api/sessions/{session.id}/activity-logs?user_id={host.id}&limit=20")
    assert list_response.status_code == 200
    logs = list_response.json()
    assert any(log["action_type"] == "session.restart" for log in logs)


def test_activity_logs_are_host_only(client, db_session):
    host = _create_user(db_session, "host_for_activity_scope")
    outsider = _create_user(db_session, "outsider_for_activity_scope")
    character = _create_character(db_session, host, "Scope Hero")
    session = _create_session(db_session, host_user_id=host.id, is_active=True)

    join_response = client.post(
        f"/api/sessions/{session.id}/join",
        json={"user_id": host.id, "character_id": character.id},
    )
    assert join_response.status_code == 200

    forbidden = client.get(f"/api/sessions/{session.id}/activity-logs?user_id={outsider.id}&limit=20")
    assert forbidden.status_code == 403
