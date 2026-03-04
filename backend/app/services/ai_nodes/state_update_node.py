import json
import logging
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_litellm import ChatLiteLLM

from app.schemas import CharacterSheet, JudgmentResult
from app.utils.prompt_loader import load_prompt

logger = logging.getLogger("ai_gm.state_update_node")


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    if "```" in raw:
        raw = raw.replace("```json", "").replace("```", "").strip()

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {"updates": []}

    payload = raw[start : end + 1]
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        logger.warning("Failed to parse state update JSON")
        return {"updates": []}

    if not isinstance(parsed, dict):
        return {"updates": []}
    updates = parsed.get("updates")
    if not isinstance(updates, list):
        parsed["updates"] = []
    return parsed


async def extract_story_state_updates(
    *,
    narrative: str,
    judgments: list[JudgmentResult],
    characters: list[CharacterSheet],
    llm_model: str,
) -> list[dict[str, Any]]:
    system_message = load_prompt("state_update_prompt.md")

    judgment_lines = []
    for judgment in judgments:
        judgment_lines.append(
            {
                "character_id": judgment.character_id,
                "action_text": judgment.action_text,
                "outcome": judgment.outcome.value,
            }
        )

    character_lines = []
    for character in characters:
        character_lines.append(
            {
                "id": character.id,
                "name": character.name,
                "statuses": character.statuses,
                "inventory": character.inventory,
            }
        )

    prompt = ChatPromptTemplate.from_messages(
        [
            system_message,
            (
                "human",
                "# Narrative\n{narrative}\n\n"
                "# Judgments\n{judgments}\n\n"
                "# Character state\n{characters}\n\n"
                "Return only JSON.",
            ),
        ]
    )

    llm = ChatLiteLLM(model=llm_model, temperature=0.1, max_tokens=2000)
    chain = prompt | llm

    try:
        response = await chain.ainvoke(
            {
                "narrative": narrative,
                "judgments": json.dumps(judgment_lines, ensure_ascii=False),
                "characters": json.dumps(character_lines, ensure_ascii=False),
            }
        )
    except Exception as exc:
        logger.warning(f"State update extraction call failed: {exc}")
        return []

    content = response.content if isinstance(response.content, str) else str(response.content)
    parsed = _extract_json_object(content)
    updates = parsed.get("updates", [])
    if not isinstance(updates, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in updates:
        if not isinstance(item, dict):
            continue
        character_id = item.get("character_id")
        if not isinstance(character_id, int):
            continue
        normalized.append(item)
    return normalized
