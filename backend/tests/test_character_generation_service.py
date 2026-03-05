from app.services.character_generation_service import normalize_generated_character_payload


def test_normalize_generated_character_payload_enforces_requested_constraints():
    raw = {
        "name": "  ",
        "age": 140,
        "race_name": "엘프",
        "gender": "male",
        "race_description": "장수 종족",
        "concept_background": "고대 유적을 탐사하는 냉정한 학자",
        "strong_ability": "intelligence",
        "weak_ability": "strength",
        "ability_scores": {
            "strength": 2,
            "dexterity": 20,
            "constitution": 100,
            "intelligence": -5,
            "wisdom": 3,
            "charisma": 12,
        },
        "passive_skills": [
            {"name": "현장 분석", "description": "단서를 빠르게 연결한다.", "ability": "intelligence"},
            {"name": "집중 유지", "description": "장시간 탐색에도 흔들리지 않는다.", "ability": "wisdom"},
        ],
        "active_skills": [
            {"name": "룬 해독", "description": "고대 문자 구조를 분해해 읽어낸다.", "ability": "intelligence"},
        ],
    }

    result = normalize_generated_character_payload(raw, "유적을 분석하는 학자형 캐릭터")

    ability_values = [result[key] for key in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")]
    assert all(7 <= value <= 11 for value in ability_values)
    assert sum(ability_values) == 54

    skills = result["skills"]
    passive = [skill for skill in skills if skill.get("type") == "passive"]
    active = [skill for skill in skills if skill.get("type") == "active"]
    assert len(passive) == 3
    assert len(active) == 2
    assert any("약점" in str(skill.get("name", "")) for skill in passive)

    assert result["statuses"] == []
    assert result["inventory"] == []
    assert result["weaknesses"] == []
    assert "남성" in result["race"]
    assert "(" in result["race"] and ")" in result["race"]
