"""Story image generation service."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

import litellm
from sqlalchemy.orm import Session

from app.models import Character, GameSession, SessionParticipant, StoryLog
from app.services.llm_config_resolver import get_active_llm_model
from app.utils.prompt_loader import PromptLoader

logger = logging.getLogger("ai_gm.socket")


class StoryImageGenerationError(Exception):
    """Raised when story image generation fails."""


def _extract_ability(data: dict[str, Any], key: str, legacy_key: str) -> int:
    value = data.get(key)
    if isinstance(value, int):
        return value
    ability_scores = data.get("ability_scores", {})
    legacy_value = ability_scores.get(legacy_key) if isinstance(ability_scores, dict) else None
    if isinstance(legacy_value, int):
        return legacy_value
    return 10


def _pick_list_values(raw: Any, *, key: str = "name", max_items: int = 5) -> list[str]:
    if raw is None:
        return []

    normalized: list[str] = []
    if isinstance(raw, dict):
        normalized = [str(k).strip() for k in raw.keys()]
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                normalized.append(item.strip())
            elif isinstance(item, dict):
                value = item.get(key) or item.get("description") or item.get("type")
                if value:
                    normalized.append(str(value).strip())

    return [item for item in normalized if item][:max_items]


def _summarize_character(character: Character) -> str:
    data = character.data if isinstance(character.data, dict) else {}
    abilities = {
        "STR": _extract_ability(data, "strength", "STR"),
        "DEX": _extract_ability(data, "dexterity", "DEX"),
        "CON": _extract_ability(data, "constitution", "CON"),
        "INT": _extract_ability(data, "intelligence", "INT"),
        "WIS": _extract_ability(data, "wisdom", "WIS"),
        "CHA": _extract_ability(data, "charisma", "CHA"),
    }
    concept = str(data.get("concept") or "").strip()
    race = str(data.get("race") or "").strip()
    skills = _pick_list_values(data.get("skills"))
    statuses = _pick_list_values(data.get("statuses")) or _pick_list_values(data.get("status_effects"))
    inventory = _pick_list_values(data.get("inventory"))

    ability_text = ", ".join(f"{name} {value}" for name, value in abilities.items())
    tags = []
    if race:
        tags.append(f"race={race}")
    if concept:
        tags.append(f"concept={concept}")
    meta = ", ".join(tags) if tags else "none"
    skills_text = ", ".join(skills) if skills else "none"
    statuses_text = ", ".join(statuses) if statuses else "none"
    inventory_text = ", ".join(inventory) if inventory else "none"

    return (
        f"- {character.name}\n"
        f"  - meta: {meta}\n"
        f"  - stats: {ability_text}\n"
        f"  - skills: {skills_text}\n"
        f"  - status: {statuses_text}\n"
        f"  - items: {inventory_text}"
    )


@lru_cache(maxsize=1)
def _get_story_image_prompt_template() -> str:
    return PromptLoader("story_image_generation_prompt.md").content


def _build_prompt(story_text: str, characters: list[Character], image_concept: str) -> str:
    compact_story = story_text.strip()[:2600]
    summaries = "\n".join(_summarize_character(c) for c in characters) or "- No character sheet available"
    compact_concept = image_concept.strip()[:1600]
    if not compact_concept:
        compact_concept = (
            "Mood: grounded fantasy adventure. "
            "Art Style: painterly realism. "
            "Negative Constraints: no text, no watermark, no UI."
        )

    template = _get_story_image_prompt_template()
    return template.format(
        image_concept=compact_concept,
        story_text=compact_story or "No story text provided.",
        character_summaries=summaries,
    )


def _to_plain_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    if hasattr(value, "dict"):
        dumped = value.dict()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _extract_image_url(response: Any) -> str:
    payload = _to_plain_dict(response)
    data_items = payload.get("data")
    if not isinstance(data_items, list) or not data_items:
        raise StoryImageGenerationError("이미지 생성 응답에서 data를 찾을 수 없습니다")

    first_item = _to_plain_dict(data_items[0])
    url = first_item.get("url")
    if isinstance(url, str) and url.strip():
        return url.strip()

    b64_json = first_item.get("b64_json")
    if isinstance(b64_json, str) and b64_json.strip():
        return f"data:image/png;base64,{b64_json.strip()}"

    raise StoryImageGenerationError("이미지 URL(b64 포함)을 찾을 수 없습니다")


async def generate_story_image_for_log(db: Session, session_id: int, story_log_id: int) -> dict[str, str]:
    session = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not session:
        raise StoryImageGenerationError("세션을 찾을 수 없습니다")

    story_log = (
        db.query(StoryLog)
        .filter(
            StoryLog.id == story_log_id,
            StoryLog.session_id == session_id,
        )
        .first()
    )
    if not story_log:
        raise StoryImageGenerationError("이미지 생성 대상 스토리를 찾을 수 없습니다")
    if story_log.role != "AI":
        raise StoryImageGenerationError("AI 스토리 메시지에 대해서만 이미지를 생성할 수 있습니다")

    participant_rows = db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id).all()
    character_ids = [row.character_id for row in participant_rows]
    characters: list[Character] = []
    if character_ids:
        characters = db.query(Character).filter(Character.id.in_(character_ids)).all()

    prompt = _build_prompt(story_log.content, characters, session.image_concept or "")
    model_id = get_active_llm_model("image")
    image_size = os.getenv("IMAGE_GENERATION_SIZE", "1024x1024")

    logger.info(
        f"스토리 이미지 생성 요청: session={session_id}, story_log={story_log_id}, model={model_id}, size={image_size}"
    )

    try:
        response = await litellm.aimage_generation(
            model=model_id,
            prompt=prompt,
            size=image_size,
            n=1,
        )
    except Exception as e:
        raise StoryImageGenerationError(f"이미지 생성 호출 실패: {e}") from e

    image_url = _extract_image_url(response)
    logger.info(f"스토리 이미지 생성 완료: session={session_id}, story_log={story_log_id}, model={model_id}")
    return {"image_url": image_url, "model_id": model_id}
