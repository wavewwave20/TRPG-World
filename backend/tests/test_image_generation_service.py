from types import SimpleNamespace

from app.services.image_generation_service import _build_prompt


def test_build_prompt_includes_session_concept_story_and_character_summary():
    characters = [
        SimpleNamespace(
            name="아리아",
            data={
                "race": "인간",
                "concept": "도시 뒷골목 정보상",
                "strength": 8,
                "dexterity": 11,
                "constitution": 9,
                "intelligence": 11,
                "wisdom": 10,
                "charisma": 9,
                "skills": [{"name": "은밀 이동"}],
                "statuses": [{"name": "긴장"}],
                "inventory": [{"name": "단검"}],
            },
        )
    ]

    prompt = _build_prompt(
        story_text="아리아가 골목 끝 그림자에서 추격자를 따돌린다.",
        characters=characters,
        image_concept="Mood: gritty urban fantasy. Art Style: painterly realism.",
    )

    assert "Mood: gritty urban fantasy. Art Style: painterly realism." in prompt
    assert "아리아가 골목 끝 그림자에서 추격자를 따돌린다." in prompt
    assert "아리아" in prompt
    assert "No text, logo, watermark, UI" in prompt
