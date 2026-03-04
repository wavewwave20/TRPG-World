import json

from app.schemas import CharacterSheet
from app.services.ai_nodes.act_analysis_node import _parse_growth_rewards


def _build_character(character_id: int, name: str) -> CharacterSheet:
    return CharacterSheet(
        id=character_id,
        name=name,
        strength=10,
        dexterity=10,
        constitution=10,
        intelligence=10,
        wisdom=10,
        charisma=10,
        skills=[],
        weaknesses=[],
        status_effects=[],
        statuses=[],
        inventory=[],
    )


def test_parse_growth_rewards_normalizes_invalid_ability_increase_detail():
    response_text = json.dumps(
        [
            {
                "character_id": 1,
                "growth_type": "ability_increase",
                "growth_detail": {"ability": "luck", "delta": -3},
                "narrative_reason": "운이 올랐다.",
            }
        ]
    )

    rewards = _parse_growth_rewards(response_text, [_build_character(1, "Tester")])

    assert len(rewards) == 1
    assert rewards[0].growth_type == "ability_increase"
    assert rewards[0].growth_detail["ability"] == "constitution"
    assert rewards[0].growth_detail["delta"] == 1


def test_parse_growth_rewards_casts_numeric_delta_and_fills_character_name():
    response_text = json.dumps(
        [
            {
                "character_id": 1,
                "growth_type": "ability_increase",
                "growth_detail": {"ability": "strength", "delta": "2"},
                "character_name": "",
                "narrative_reason": "전투를 통해 근력이 향상됐다.",
            }
        ]
    )

    rewards = _parse_growth_rewards(response_text, [_build_character(1, "Fighter")])

    assert len(rewards) == 1
    assert rewards[0].character_name == "Fighter"
    assert rewards[0].growth_detail == {"ability": "strength", "delta": 2}


def test_parse_growth_rewards_adds_fallback_ability_reward_when_only_new_skill_exists():
    response_text = json.dumps(
        [
            {
                "character_id": 1,
                "growth_type": "new_skill",
                "growth_detail": {"skill": {"type": "active", "name": "예리한 감각"}},
                "narrative_reason": "위기를 넘기며 감각이 예리해졌다.",
            }
        ]
    )

    rewards = _parse_growth_rewards(response_text, [_build_character(1, "Scout")])

    assert len(rewards) == 2
    assert any(r.growth_type == "new_skill" for r in rewards)

    ability_reward = next(r for r in rewards if r.growth_type == "ability_increase")
    assert ability_reward.growth_detail == {"ability": "constitution", "delta": 1}
