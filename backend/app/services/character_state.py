from typing import Any


VALID_STATUS_TYPES = {"buff", "debuff"}
VALID_ITEM_TYPES = {"consumable", "equipment"}


def normalize_inventory_items(raw_inventory: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_inventory, list):
        return []

    items: list[dict[str, Any]] = []
    for raw in raw_inventory:
        if isinstance(raw, str):
            name = raw.strip()
            if not name:
                continue
            items.append({"name": name, "quantity": 1, "type": "equipment", "equipped": False})
            continue

        if not isinstance(raw, dict):
            continue

        name = str(raw.get("name") or "").strip()
        if not name:
            continue

        quantity_raw = raw.get("quantity", 1)
        try:
            quantity = int(quantity_raw)
        except (TypeError, ValueError):
            quantity = 1

        item_type = str(raw.get("type") or "equipment").strip().lower()
        if item_type not in VALID_ITEM_TYPES:
            item_type = "equipment"

        normalized_quantity = max(1, quantity)
        if item_type == "equipment":
            normalized_quantity = 1

        item = {
            "name": name,
            "quantity": normalized_quantity,
            "type": item_type,
            "equipped": bool(raw.get("equipped", False)) if item_type == "equipment" else False,
        }

        modifier = raw.get("modifier")
        if isinstance(modifier, int):
            item["modifier"] = modifier

        action_modifiers = raw.get("action_modifiers")
        if isinstance(action_modifiers, dict):
            item["action_modifiers"] = {str(k): v for k, v in action_modifiers.items() if isinstance(v, int)}

        description = raw.get("description")
        if isinstance(description, str) and description.strip():
            item["description"] = description.strip()

        raw_status = raw.get("status")
        parsed_status = _parse_status(raw_status)
        if parsed_status is not None:
            item["status"] = parsed_status

        items.append(item)

    return items


def normalize_statuses(
    data: dict[str, Any] | None,
    *,
    include_legacy_status_effects: bool = True,
) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []

    normalized: list[dict[str, Any]] = []

    statuses = data.get("statuses", [])
    if isinstance(statuses, list):
        for raw in statuses:
            parsed = _parse_status(raw)
            if parsed is not None:
                normalized.append(parsed)

    if include_legacy_status_effects:
        status_effects = data.get("status_effects", [])
        if isinstance(status_effects, list):
            for raw in status_effects:
                parsed = _parse_status(raw)
                if parsed is not None:
                    normalized.append(parsed)

    inventory_items = normalize_inventory_items(data.get("inventory", []))
    normalized.extend(_statuses_from_inventory(inventory_items))

    weaknesses = data.get("weaknesses", [])
    if isinstance(weaknesses, list):
        for weakness in weaknesses:
            name = None
            if isinstance(weakness, str):
                weak_name = weakness.strip()
                if weak_name:
                    name = weak_name
            elif isinstance(weakness, dict):
                raw_name = weakness.get("name") or weakness.get("description")
                if isinstance(raw_name, str) and raw_name.strip():
                    name = raw_name.strip()

            if not name:
                continue

            normalized.append(
                {
                    "name": name,
                    "category": "mental",
                    "type": "debuff",
                    "modifier": -1,
                    "source": "weakness",
                }
            )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for status in normalized:
        key = (
            str(status.get("name", "")).strip().lower(),
            str(status.get("type", "debuff")).strip().lower(),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        deduped.append(status)

    return deduped


def status_modifier_for_action(statuses: list[Any], action_type_value: str) -> int:
    total = 0
    for raw in statuses:
        if not isinstance(raw, dict):
            continue

        applies_to = raw.get("applies_to")
        if isinstance(applies_to, list) and applies_to:
            normalized_targets = {str(target).strip().lower() for target in applies_to}
            if action_type_value not in normalized_targets and "all" not in normalized_targets:
                continue

        modifier = raw.get("modifier", 0)
        if isinstance(modifier, int):
            total += modifier

    return total


def inventory_modifier_for_action(inventory_items: list[dict[str, Any]], action_type_value: str) -> int:
    total = 0
    for item in inventory_items:
        if not isinstance(item, dict):
            continue

        if str(item.get("type") or "equipment").strip().lower() != "equipment":
            continue

        if not bool(item.get("equipped", False)):
            continue

        action_modifiers = item.get("action_modifiers")
        if isinstance(action_modifiers, dict):
            ability_modifier = action_modifiers.get(action_type_value)
            if isinstance(ability_modifier, int):
                total += ability_modifier

        generic_modifier = item.get("modifier")
        if isinstance(generic_modifier, int):
            total += generic_modifier

    return total


def _parse_status(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, str):
        name = raw.strip()
        if not name:
            return None
        return {
            "name": name,
            "category": "physical",
            "type": "debuff",
            "modifier": 0,
            "source": "legacy",
        }

    if not isinstance(raw, dict):
        return None

    name = str(raw.get("name") or raw.get("description") or "").strip()
    if not name:
        return None

    default_modifier = raw.get("modifier", 0)
    default_modifier = default_modifier if isinstance(default_modifier, int) else 0

    status_type = str(raw.get("type") or ("buff" if default_modifier > 0 else "debuff")).strip().lower()
    if status_type not in VALID_STATUS_TYPES:
        status_type = "debuff"

    category = str(raw.get("category") or "physical").strip().lower()
    if category not in {"physical", "mental", "social", "environment"}:
        category = "physical"

    modifier = default_modifier

    normalized = {
        "name": name,
        "category": category,
        "type": status_type,
        "modifier": modifier,
        "source": str(raw.get("source") or "status"),
    }

    applies_to = raw.get("applies_to")
    if isinstance(applies_to, list) and applies_to:
        normalized["applies_to"] = [str(target).strip().lower() for target in applies_to]

    description = raw.get("description")
    if isinstance(description, str) and description.strip():
        normalized["description"] = description.strip()

    return normalized


def _statuses_from_inventory(inventory_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    derived: list[dict[str, Any]] = []
    for item in inventory_items:
        if not isinstance(item, dict):
            continue

        if str(item.get("type") or "equipment").strip().lower() != "equipment":
            continue

        if not bool(item.get("equipped", False)):
            continue

        status = item.get("status")
        parsed = _parse_status(status)
        if parsed is not None:
            parsed["source"] = f"inventory:{item.get('name', '')}"
            derived.append(parsed)
            continue

        item_modifier = item.get("modifier")
        if isinstance(item_modifier, int) and item_modifier != 0:
            item_name = str(item.get("name") or "").strip()
            if not item_name:
                continue
            derived.append(
                {
                    "name": item_name,
                    "category": "physical",
                    "type": "buff" if item_modifier > 0 else "debuff",
                    "modifier": item_modifier,
                    "source": f"inventory:{item_name}",
                }
            )

    return derived


def consume_inventory_item(raw_inventory: Any, item_name: str) -> list[dict[str, Any]]:
    items = normalize_inventory_items(raw_inventory)
    target = item_name.strip().lower()
    if not target:
        return items

    updated: list[dict[str, Any]] = []
    consumed = False
    for item in items:
        if consumed:
            updated.append(item)
            continue

        normalized_name = str(item.get("name") or "").strip().lower()
        item_type = str(item.get("type") or "equipment").strip().lower()
        if item_type == "consumable" and normalized_name == target:
            quantity = int(item.get("quantity", 1))
            if quantity > 1:
                next_item = dict(item)
                next_item["quantity"] = quantity - 1
                updated.append(next_item)
            consumed = True
            continue

        updated.append(item)

    return updated
