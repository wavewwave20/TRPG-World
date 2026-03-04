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
