"""AI-assisted character generation service."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_litellm import ChatLiteLLM

from app.services.llm_config_resolver import get_active_llm_model
from app.utils.prompt_loader import load_prompt

logger = logging.getLogger("ai_gm.character_generation")

ABILITY_KEYS = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
ABILITY_OPPOSITES = {
    "strength": "intelligence",
    "dexterity": "constitution",
    "constitution": "dexterity",
    "intelligence": "strength",
    "wisdom": "charisma",
    "charisma": "wisdom",
}
ABILITY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "strength": ("근력", "힘", "전사", "검", "창", "망치", "격투", "warrior", "fighter", "brute", "tank"),
    "dexterity": ("민첩", "은신", "도적", "궁수", "사격", "곡예", "rogue", "archer", "sniper", "agile", "stealth"),
    "constitution": ("건강", "체력", "버티", "맷집", "인내", "생존", "vitality", "stamina", "endure", "survive"),
    "intelligence": ("지능", "학자", "연구", "분석", "마법", "공학", "wizard", "mage", "engineer", "logic", "arcane"),
    "wisdom": ("지혜", "통찰", "추적", "치유", "사제", "명상", "druid", "cleric", "insight", "instinct", "sense"),
    "charisma": ("매력", "협상", "연설", "지휘", "사교", "속임", "bard", "leader", "charm", "persuade", "perform"),
}
WEAKNESS_HINTS = ("약점", "취약", "허약", "불안", "공포", "집착", "결핍", "불리", "맹점", "패닉")


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    if "```" in raw:
        raw = raw.replace("```json", "").replace("```", "").strip()

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}

    try:
        parsed = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        logger.warning("AI character generation JSON parse failed")
        return {}

    if not isinstance(parsed, dict):
        return {}
    if isinstance(parsed.get("character"), dict):
        return parsed["character"]
    return parsed


def _normalize_ability_key(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in ABILITY_KEYS:
        return text
    alias = {
        "str": "strength",
        "dex": "dexterity",
        "con": "constitution",
        "int": "intelligence",
        "wis": "wisdom",
        "cha": "charisma",
        "근력": "strength",
        "민첩": "dexterity",
        "건강": "constitution",
        "지능": "intelligence",
        "지혜": "wisdom",
        "매력": "charisma",
    }
    return alias.get(text)


def _normalize_gender(value: Any, concept_text: str) -> str:
    text = str(value or "").strip().lower()
    if any(token in text for token in ("female", "woman", "여성", "여자")):
        return "여성"
    if any(token in text for token in ("male", "man", "남성", "남자")):
        return "남성"
    if any(token in text for token in ("non-binary", "논바이너리", "중성")):
        return "논바이너리"

    concept = concept_text.lower()
    if any(token in concept for token in ("여성", "여자", "female", "woman")):
        return "여성"
    if any(token in concept for token in ("남성", "남자", "male", "man")):
        return "남성"
    return "논바이너리"


def _infer_strong_and_weak_abilities(concept_text: str, raw: dict[str, Any]) -> tuple[str, str]:
    raw_strong = _normalize_ability_key(raw.get("strong_ability"))
    raw_weak = _normalize_ability_key(raw.get("weak_ability"))
    if raw_strong and raw_weak and raw_strong != raw_weak:
        return raw_strong, raw_weak

    lowered = concept_text.lower()
    score_map = {key: 0 for key in ABILITY_KEYS}
    for key, keywords in ABILITY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in lowered:
                score_map[key] += 1

    strong = max(ABILITY_KEYS, key=lambda key: score_map[key])
    weak = ABILITY_OPPOSITES.get(strong, "charisma")
    if weak == strong:
        weak = "charisma" if strong != "charisma" else "strength"
    return strong, weak


def _build_balanced_ability_scores(raw_scores: Any, strong: str, weak: str) -> dict[str, int]:
    scores = {key: 9 for key in ABILITY_KEYS}

    if isinstance(raw_scores, dict):
        for key in ABILITY_KEYS:
            raw_value = raw_scores.get(key)
            if raw_value is None:
                continue
            try:
                parsed = int(raw_value)
            except (TypeError, ValueError):
                continue
            scores[key] = max(7, min(11, parsed))

    scores[strong] = 11
    scores[weak] = 7

    def _increase_one() -> bool:
        order = [key for key in ABILITY_KEYS if key != weak] + [weak]
        for key in order:
            if scores[key] < 11:
                scores[key] += 1
                return True
        return False

    def _decrease_one() -> bool:
        order = [key for key in ABILITY_KEYS if key != strong] + [strong]
        for key in order:
            if scores[key] > 7:
                scores[key] -= 1
                return True
        return False

    while sum(scores.values()) < 54 and _increase_one():
        pass
    while sum(scores.values()) > 54 and _decrease_one():
        pass

    if sum(scores.values()) != 54:
        scores = {key: 9 for key in ABILITY_KEYS}
        scores[strong] = 11
        scores[weak] = 7

    return scores


def _sanitize_skill(raw: Any, *, skill_type: str, fallback_name: str, fallback_description: str, ability: str) -> dict[str, Any]:
    if isinstance(raw, dict):
        name = str(raw.get("name") or "").strip()
        description = str(raw.get("description") or "").strip()
        ability_key = _normalize_ability_key(raw.get("ability")) or ability
    else:
        name = ""
        description = ""
        ability_key = ability

    if not name:
        name = fallback_name
    if not description:
        description = fallback_description

    return {
        "type": skill_type,
        "name": name,
        "description": description,
        "ability": ability_key,
    }


def _contains_weakness_hint(skill: dict[str, Any]) -> bool:
    text = f"{skill.get('name', '')} {skill.get('description', '')}".lower()
    return any(hint in text for hint in WEAKNESS_HINTS)


def _normalize_skills(raw: dict[str, Any], *, strong: str, weak: str) -> list[dict[str, Any]]:
    passive_candidates: list[Any] = []
    active_candidates: list[Any] = []

    if isinstance(raw.get("skills"), list):
        for item in raw["skills"]:
            if not isinstance(item, dict):
                continue
            skill_type = str(item.get("type") or "").strip().lower()
            if skill_type == "active":
                active_candidates.append(item)
            else:
                passive_candidates.append(item)

    if isinstance(raw.get("passive_skills"), list):
        passive_candidates.extend(raw["passive_skills"])
    if isinstance(raw.get("active_skills"), list):
        active_candidates.extend(raw["active_skills"])

    passive_defaults = [
        ("전투 감각", "위험을 빠르게 감지해 선제적으로 대응한다.", "wisdom"),
        ("숙련된 기본기", "주 무기/주문의 기본 동작에 높은 숙련을 보인다.", strong),
        ("긴장성 강박", "압박이 높아질수록 시야가 좁아져 판단이 단선적이 된다.", weak),
    ]
    active_defaults = [
        ("결정타", "핵심 순간에 전력을 집중해 강한 한 방을 시도한다.", strong),
        ("즉응 기동", "짧은 순간 위치를 재정비해 유리한 각을 만든다.", "dexterity"),
    ]

    seen: set[str] = set()
    passives: list[dict[str, Any]] = []
    for idx, item in enumerate(passive_candidates):
        fallback = passive_defaults[min(idx, len(passive_defaults) - 1)]
        skill = _sanitize_skill(
            item,
            skill_type="passive",
            fallback_name=fallback[0],
            fallback_description=fallback[1],
            ability=fallback[2],
        )
        key = skill["name"].strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        passives.append(skill)
        if len(passives) == 3:
            break

    while len(passives) < 3:
        fallback = passive_defaults[len(passives)]
        skill = _sanitize_skill(
            {},
            skill_type="passive",
            fallback_name=fallback[0],
            fallback_description=fallback[1],
            ability=fallback[2],
        )
        key = skill["name"].strip().lower()
        if key in seen:
            skill["name"] = f"{skill['name']} {len(passives) + 1}"
            key = skill["name"].strip().lower()
        seen.add(key)
        passives.append(skill)

    actives: list[dict[str, Any]] = []
    for idx, item in enumerate(active_candidates):
        fallback = active_defaults[min(idx, len(active_defaults) - 1)]
        skill = _sanitize_skill(
            item,
            skill_type="active",
            fallback_name=fallback[0],
            fallback_description=fallback[1],
            ability=fallback[2],
        )
        key = skill["name"].strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        actives.append(skill)
        if len(actives) == 2:
            break

    while len(actives) < 2:
        fallback = active_defaults[len(actives)]
        skill = _sanitize_skill(
            {},
            skill_type="active",
            fallback_name=fallback[0],
            fallback_description=fallback[1],
            ability=fallback[2],
        )
        key = skill["name"].strip().lower()
        if key in seen:
            skill["name"] = f"{skill['name']} {len(actives) + 1}"
            key = skill["name"].strip().lower()
        seen.add(key)
        actives.append(skill)

    if not any(_contains_weakness_hint(skill) for skill in passives):
        weakest = passives[-1]
        if not str(weakest.get("name", "")).startswith("약점:"):
            weakest["name"] = f"약점: {weakest['name']}"
        description = str(weakest.get("description") or "").strip()
        if "불리" not in description and "약점" not in description:
            weakest["description"] = f"{description} 중요한 순간에는 이 성향이 명확한 약점으로 작동해 불리해질 수 있다."
        weakest["ability"] = weak

    return passives + actives


def _normalize_name(raw: dict[str, Any], concept_text: str) -> str:
    name = str(raw.get("name") or "").strip()
    if name:
        return name[:40]

    compact = re.sub(r"[^0-9A-Za-z가-힣 ]+", " ", concept_text).strip()
    if compact:
        base = compact.split()[0][:10]
        return f"{base}의 모험가"
    return "이름없는 모험가"


def _normalize_age(raw: dict[str, Any]) -> int:
    try:
        value = int(raw.get("age", 25))
    except (TypeError, ValueError):
        value = 25
    return max(12, min(80, value))


def _normalize_race(raw: dict[str, Any], concept_text: str) -> str:
    species = str(raw.get("race_name") or raw.get("race") or "").strip() or "인간"
    gender = _normalize_gender(raw.get("gender"), concept_text)
    description = str(raw.get("race_description") or "").strip()
    if not description:
        description = "겉보기 특징과 생활권이 뚜렷한 개체"
    return f"{species} {gender} ({description})"


def _normalize_concept(raw: dict[str, Any], concept_text: str) -> str:
    concept = str(raw.get("concept_background") or raw.get("concept") or "").strip()
    if concept:
        return concept
    return concept_text.strip()


def normalize_generated_character_payload(raw_payload: dict[str, Any], concept_text: str) -> dict[str, Any]:
    raw = raw_payload if isinstance(raw_payload, dict) else {}
    strong, weak = _infer_strong_and_weak_abilities(concept_text, raw)
    if strong == weak:
        weak = ABILITY_OPPOSITES.get(strong, "charisma")

    ability_scores = _build_balanced_ability_scores(raw.get("ability_scores"), strong, weak)
    skills = _normalize_skills(raw, strong=strong, weak=weak)

    return {
        "name": _normalize_name(raw, concept_text),
        "age": _normalize_age(raw),
        "race": _normalize_race(raw, concept_text),
        "concept": _normalize_concept(raw, concept_text),
        "strength": ability_scores["strength"],
        "dexterity": ability_scores["dexterity"],
        "constitution": ability_scores["constitution"],
        "intelligence": ability_scores["intelligence"],
        "wisdom": ability_scores["wisdom"],
        "charisma": ability_scores["charisma"],
        "skills": skills,
        "weaknesses": [],
        "statuses": [],
        "inventory": [],
    }


async def generate_character_from_concept(concept_text: str) -> dict[str, Any]:
    concept = concept_text.strip()
    if not concept:
        raise ValueError("concept_text is required")

    model_id = get_active_llm_model("judgment")
    system_message = load_prompt("character_generation_prompt.md")
    prompt = ChatPromptTemplate.from_messages(
        [
            system_message,
            (
                "human",
                "# 유저 컨셉 설명\n{concept_text}\n\nJSON만 반환하세요.",
            ),
        ]
    )
    llm = ChatLiteLLM(model=model_id, temperature=0.6, max_tokens=2200)
    chain = prompt | llm

    raw_payload: dict[str, Any] = {}
    try:
        response = await chain.ainvoke({"concept_text": concept})
        content = response.content if isinstance(response.content, str) else str(response.content)
        raw_payload = _extract_json_object(content)
    except Exception as exc:
        logger.warning(f"AI character generation failed, fallback to heuristic generation: {exc}")

    generated = normalize_generated_character_payload(raw_payload, concept)
    logger.info(f"AI character generated with model={model_id}, name={generated['name']}")
    return generated
