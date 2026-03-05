from app.services.character_state import (
    inventory_modifier_for_action,
    normalize_inventory_items,
    normalize_statuses,
    status_modifier_for_action,
)


def test_normalize_statuses_includes_weakness_as_debuff():
    data = {
        "weaknesses": ["Fear of darkness"],
        "status_effects": [{"name": "Blessed", "modifier": 2}],
    }

    statuses = normalize_statuses(data)

    names = {s["name"] for s in statuses}
    assert "Fear of darkness" in names
    assert "Blessed" in names

    weakness = next(s for s in statuses if s["name"] == "Fear of darkness")
    assert weakness["type"] == "debuff"
    assert weakness["modifier"] == -1


def test_status_modifier_applies_action_filter():
    statuses = [
        {"name": "A", "modifier": 2, "applies_to": ["strength"]},
        {"name": "B", "modifier": -1, "applies_to": ["dexterity"]},
        {"name": "C", "modifier": 1},
    ]

    assert status_modifier_for_action(statuses, "strength") == 3
    assert status_modifier_for_action(statuses, "dexterity") == 0


def test_normalize_inventory_items_and_equipped_modifier():
    raw_inventory = [
        "Torch",
        {
            "name": "Ring of Power",
            "equipped": True,
            "modifier": 1,
            "action_modifiers": {"charisma": 2, "strength": "bad"},
        },
        {
            "name": "Heavy Shield",
            "equipped": False,
            "modifier": 5,
        },
    ]

    items = normalize_inventory_items(raw_inventory)

    assert items[0]["name"] == "Torch"
    assert items[0]["quantity"] == 1
    assert items[0]["type"] == "equipment"

    assert inventory_modifier_for_action(items, "charisma") == 3
    assert inventory_modifier_for_action(items, "strength") == 1


def test_normalize_statuses_keeps_description_and_applies_to():
    statuses = normalize_statuses(
        {
            "statuses": [
                {
                    "name": "집중",
                    "type": "buff",
                    "modifier": 2,
                    "description": "정신을 가다듬어 시야를 확보함",
                    "applies_to": ["dexterity", "wisdom"],
                }
            ]
        },
        include_legacy_status_effects=False,
    )

    assert len(statuses) == 1
    assert statuses[0]["name"] == "집중"
    assert statuses[0]["description"] == "정신을 가다듬어 시야를 확보함"
    assert statuses[0]["applies_to"] == ["dexterity", "wisdom"]


def test_normalize_inventory_items_keeps_description():
    items = normalize_inventory_items(
        [
            {
                "name": "은빛 단검",
                "type": "equipment",
                "equipped": True,
                "modifier": 1,
                "description": "언데드에게 특히 잘 먹히는 축성 무기",
            }
        ]
    )

    assert len(items) == 1
    assert items[0]["name"] == "은빛 단검"
    assert items[0]["description"] == "언데드에게 특히 잘 먹히는 축성 무기"
