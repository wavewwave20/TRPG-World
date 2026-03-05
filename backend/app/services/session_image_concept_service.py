"""Session-level image concept generation service."""

from __future__ import annotations

import logging
import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_litellm import ChatLiteLLM

from app.services.llm_config_resolver import get_active_llm_model
from app.utils.prompt_loader import load_prompt

logger = logging.getLogger("ai_gm.session_image_concept")

DEFAULT_IMAGE_CONCEPT = (
    "Mood: grounded fantasy adventure with cinematic tension.\n"
    "Art Style: painterly realism, coherent anatomy, practical costumes and props.\n"
    "Lighting/Color: directional lighting, restrained contrast, controlled color palette.\n"
    "Camera: medium-wide composition focused on action readability.\n"
    "Character Design Cues: keep race, gear, and silhouette consistent per scene.\n"
    "Negative Constraints: no text, no watermark, no UI, no extra limbs, no modern artifacts."
)


def _sanitize_concept(raw_text: str, world_prompt: str) -> str:
    text = (raw_text or "").strip()
    if "```" in text:
        text = text.replace("```text", "").replace("```md", "").replace("```", "").strip()

    # Remove trivial lead-in phrases to keep the concept concise.
    text = re.sub(r"^(here is|output:|result:)\s*", "", text, flags=re.IGNORECASE)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    normalized = "\n".join(lines)

    if not normalized:
        return get_default_image_concept(world_prompt)

    if len(normalized) > 1400:
        normalized = normalized[:1400].rstrip()

    return normalized


def get_default_image_concept(world_prompt: str) -> str:
    compact_world = re.sub(r"\s+", " ", world_prompt or "").strip()
    if compact_world:
        world_anchor = compact_world[:220]
        return f"{DEFAULT_IMAGE_CONCEPT}\nWorld Anchor: {world_anchor}"
    return DEFAULT_IMAGE_CONCEPT


async def generate_image_concept_from_world_prompt(world_prompt: str) -> str:
    world_text = (world_prompt or "").strip()
    if not world_text:
        return get_default_image_concept("")

    model_id = get_active_llm_model("story")
    system_message = load_prompt("image_concept_prompt.md")
    prompt = ChatPromptTemplate.from_messages(
        [
            system_message,
            (
                "human",
                "# Story System Prompt\n{world_prompt}\n\n"
                "Return only the final image concept text.",
            ),
        ]
    )

    llm = ChatLiteLLM(model=model_id, temperature=0.2, max_tokens=700)
    chain = prompt | llm

    try:
        response = await chain.ainvoke({"world_prompt": world_text[:12000]})
        content = response.content if isinstance(response.content, str) else str(response.content)
        concept = _sanitize_concept(content, world_text)
        logger.info("Session image concept generated successfully")
        return concept
    except Exception as exc:
        logger.warning(f"Failed to generate session image concept via LLM: {exc}")
        return get_default_image_concept(world_text)
