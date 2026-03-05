import asyncio
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Character, GameSession, User
from app.schemas import CharacterSheet
from app.services.ai_gm_service_v2 import AIGMServiceV2

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
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _base_character_data() -> dict:
    return {
        "age": 25,
        "race": "Human",
        "concept": "",
        "strength": 10,
        "dexterity": 12,
        "constitution": 10,
        "intelligence": 10,
        "wisdom": 11,
        "charisma": 9,
        "skills": [],
        "weaknesses": [],
        "statuses": [
            {
                "name": "독",
                "category": "physical",
                "type": "debuff",
                "modifier": -2,
                "description": "몸이 마비되어 행동이 둔해짐",
                "source": "story_event",
            }
        ],
        "status_effects": [],
        "inventory": [
            {
                "name": "치유 물약",
                "type": "consumable",
                "quantity": 1,
                "description": "응급 회복용 물약",
            }
        ],
    }


def test_apply_story_state_updates_keeps_status_and_inventory_descriptions(db_session, monkeypatch):
    user = User(username="tester", password="hashed", created_at=datetime.utcnow())
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    session = GameSession(
        host_user_id=user.id,
        title="테스트 세션",
        world_prompt="test prompt",
        created_at=datetime.utcnow(),
        is_active=True,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    character = Character(
        user_id=user.id,
        name="테스트 캐릭터",
        data=_base_character_data(),
        created_at=datetime.utcnow(),
    )
    db_session.add(character)
    db_session.commit()
    db_session.refresh(character)

    async def fake_extract_story_state_updates(*, narrative, judgments, characters, llm_model):
        assert narrative == "새로운 서사"
        assert llm_model == "test-model"
        assert len(characters) == 1
        return [
            {
                "character_id": character.id,
                "remove_statuses": ["독"],
                "add_statuses": [
                    {
                        "name": "집중",
                        "type": "buff",
                        "modifier": 2,
                        "description": "조준에 집중해 원거리 판정이 좋아짐",
                        "applies_to": ["dexterity"],
                    }
                ],
                "add_inventory": [
                    {
                        "name": "은빛 열쇠",
                        "type": "equipment",
                        "description": "고대 문양이 새겨진 열쇠",
                    }
                ],
            }
        ]

    monkeypatch.setattr(
        "app.services.ai_gm_service_v2.extract_story_state_updates",
        fake_extract_story_state_updates,
    )

    service = AIGMServiceV2(db_session, llm_model="test-model", judgment_model="test-model")

    game_context = type(
        "FakeGameContext",
        (),
        {
            "characters": [
                CharacterSheet(
                    id=character.id,
                    name=character.name,
                    strength=10,
                    dexterity=12,
                    constitution=10,
                    intelligence=10,
                    wisdom=11,
                    charisma=9,
                    skills=[],
                    weaknesses=[],
                    status_effects=[],
                    statuses=character.data["statuses"],
                    inventory=character.data["inventory"],
                )
            ]
        },
    )()

    asyncio.run(
        service._apply_story_state_updates(
            session_id=session.id,
            narrative="새로운 서사",
            judgments=[],
            game_context=game_context,
        )
    )

    db_session.refresh(character)
    statuses = character.data["statuses"]
    inventory = character.data["inventory"]

    assert all(status["name"] != "독" for status in statuses)

    focused = next(status for status in statuses if status["name"] == "집중")
    assert focused["description"] == "조준에 집중해 원거리 판정이 좋아짐"
    assert focused["applies_to"] == ["dexterity"]
    assert focused["source"] == "story_event"

    silver_key = next(item for item in inventory if item["name"] == "은빛 열쇠")
    assert silver_key["description"] == "고대 문양이 새겨진 열쇠"

    assert any(status["name"] == "집중" for status in character.data["status_effects"])
