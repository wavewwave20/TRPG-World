from app.services.session_image_concept_service import _sanitize_concept, get_default_image_concept


def test_get_default_image_concept_includes_world_anchor_when_prompt_exists():
    concept = get_default_image_concept("A frozen frontier kingdom under endless twilight.")
    assert "World Anchor:" in concept
    assert "frozen frontier kingdom" in concept


def test_sanitize_concept_removes_code_fence_and_trims():
    raw = "```text\nMood: dark mystery\nArt Style: painterly realism\n```"
    concept = _sanitize_concept(raw, "Any world prompt")
    assert "```" not in concept
    assert concept.startswith("Mood:")
