"""
Tests for the judgment node module (Phase 1: action analysis).

Tests cover modifier calculation from ability scores, skill proficiency bonuses,
status effect application, DC response parsing from AI output, and the full
analyze_and_judge_actions pipeline with mocked AI calls.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas import ActionAnalysis, ActionType, CharacterSheet, PlayerAction
from app.services.ai_nodes.judgment_node import (
    _calculate_modifier,
    _parse_dc_response,
    analyze_and_judge_actions,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_character() -> CharacterSheet:
    """A character with all ability scores at 10 (modifier 0) and no extras."""
    return CharacterSheet(
        id=1,
        name="Test Hero",
        strength=10,
        dexterity=10,
        constitution=10,
        intelligence=10,
        wisdom=10,
        charisma=10,
        skills=[],
        weaknesses=[],
        status_effects=[],
    )


@pytest.fixture
def skilled_character() -> CharacterSheet:
    """A character with high STR, a matching skill, and a status effect."""
    return CharacterSheet(
        id=2,
        name="Skilled Fighter",
        strength=18,
        dexterity=14,
        constitution=12,
        intelligence=8,
        wisdom=10,
        charisma=10,
        skills=[
            {"name": "Athletics", "ability": "strength"},
            {"name": "Stealth", "ability": "dexterity"},
        ],
        weaknesses=["Fear of fire"],
        status_effects=[
            {"name": "Blessed", "modifier": 2},
        ],
    )


@pytest.fixture
def sample_action() -> PlayerAction:
    return PlayerAction(
        character_id=1,
        action_text="I try to lift the boulder.",
        action_type=ActionType.STRENGTH,
    )


@pytest.fixture
def sample_characters() -> list[CharacterSheet]:
    """Two characters for multi-action tests."""
    return [
        CharacterSheet(
            id=1,
            name="Warrior",
            strength=16,
            dexterity=10,
            constitution=14,
            intelligence=10,
            wisdom=10,
            charisma=10,
            skills=[{"name": "Athletics", "ability": "strength"}],
            weaknesses=[],
            status_effects=[],
        ),
        CharacterSheet(
            id=2,
            name="Rogue",
            strength=10,
            dexterity=18,
            constitution=10,
            intelligence=12,
            wisdom=10,
            charisma=10,
            skills=[{"name": "Stealth", "ability": "dexterity"}],
            weaknesses=[],
            status_effects=[],
        ),
    ]


@pytest.fixture
def sample_actions() -> list[PlayerAction]:
    return [
        PlayerAction(
            character_id=1,
            action_text="I smash the door open.",
            action_type=ActionType.STRENGTH,
        ),
        PlayerAction(
            character_id=2,
            action_text="I sneak past the guards.",
            action_type=ActionType.DEXTERITY,
        ),
    ]


# ===========================================================================
# _calculate_modifier tests
# ===========================================================================


class TestCalculateModifier:
    """Tests for _calculate_modifier."""

    # -- Ability score mapping -----------------------------------------------

    @pytest.mark.parametrize(
        "action_type, ability_field, score, expected_modifier",
        [
            (ActionType.STRENGTH, "strength", 18, 4),
            (ActionType.DEXTERITY, "dexterity", 14, 2),
            (ActionType.CONSTITUTION, "constitution", 12, 1),
            (ActionType.INTELLIGENCE, "intelligence", 16, 3),
            (ActionType.WISDOM, "wisdom", 20, 5),
            (ActionType.CHARISMA, "charisma", 8, -1),
        ],
    )
    def test_each_ability_type_maps_to_correct_score(
        self, base_character, action_type, ability_field, score, expected_modifier
    ):
        """Each ActionType should use the corresponding ability score."""
        setattr(base_character, ability_field, score)
        result = _calculate_modifier(base_character, action_type)
        assert result == expected_modifier

    def test_average_score_gives_zero_modifier(self, base_character):
        """Score of 10 should yield modifier 0."""
        assert _calculate_modifier(base_character, ActionType.STRENGTH) == 0

    def test_odd_score_uses_floor_division(self, base_character):
        """Score of 11 -> (11 - 10) // 2 = 0, score of 15 -> (15 - 10) // 2 = 2."""
        base_character.strength = 11
        assert _calculate_modifier(base_character, ActionType.STRENGTH) == 0

        base_character.strength = 15
        assert _calculate_modifier(base_character, ActionType.STRENGTH) == 2

    def test_minimum_score(self, base_character):
        """Score of 1 -> (1 - 10) // 2 = -5 (floor division of -9)."""
        base_character.strength = 1
        assert _calculate_modifier(base_character, ActionType.STRENGTH) == -5

    def test_maximum_score(self, base_character):
        """Score of 30 -> (30 - 10) // 2 = 10."""
        base_character.strength = 30
        assert _calculate_modifier(base_character, ActionType.STRENGTH) == 10

    # -- Skill proficiency bonus (+2) ----------------------------------------

    def test_skill_proficiency_bonus_when_ability_matches(self, base_character):
        """A skill whose ability matches the action_type should add +2."""
        base_character.strength = 14  # modifier = 2
        base_character.skills = [{"name": "Athletics", "ability": "strength"}]
        result = _calculate_modifier(base_character, ActionType.STRENGTH)
        assert result == 4  # 2 (ability) + 2 (proficiency)

    def test_no_skill_bonus_when_ability_differs(self, base_character):
        """A skill whose ability does not match should not add a bonus."""
        base_character.strength = 14  # modifier = 2
        base_character.skills = [{"name": "Stealth", "ability": "dexterity"}]
        result = _calculate_modifier(base_character, ActionType.STRENGTH)
        assert result == 2  # No proficiency bonus

    def test_no_duplicate_skill_bonus(self, base_character):
        """Only the first matching skill should contribute the +2 bonus."""
        base_character.strength = 14  # modifier = 2
        base_character.skills = [
            {"name": "Athletics", "ability": "strength"},
            {"name": "Heavy Lifting", "ability": "strength"},
        ]
        result = _calculate_modifier(base_character, ActionType.STRENGTH)
        assert result == 4  # 2 + 2, NOT 2 + 4

    def test_skill_without_ability_key_gives_no_bonus(self, base_character):
        """A skill dict missing the 'ability' key should not add a bonus."""
        base_character.strength = 14
        base_character.skills = [{"name": "Cooking"}]
        result = _calculate_modifier(base_character, ActionType.STRENGTH)
        assert result == 2

    def test_skill_with_none_ability_gives_no_bonus(self, base_character):
        """A skill with ability=None should not add a bonus."""
        base_character.strength = 14
        base_character.skills = [{"name": "Cooking", "ability": None}]
        result = _calculate_modifier(base_character, ActionType.STRENGTH)
        assert result == 2

    # -- Status effects ------------------------------------------------------

    def test_status_effect_dict_with_modifier_applied(self, base_character):
        """A status effect dict with a 'modifier' field should be applied."""
        base_character.status_effects = [{"name": "Blessed", "modifier": 3}]
        result = _calculate_modifier(base_character, ActionType.STRENGTH)
        assert result == 3  # 0 (ability) + 3 (status effect)

    def test_status_effect_negative_modifier(self, base_character):
        """Negative status effect modifier should reduce the total."""
        base_character.status_effects = [{"name": "Cursed", "modifier": -2}]
        result = _calculate_modifier(base_character, ActionType.STRENGTH)
        assert result == -2  # 0 (ability) - 2 (status effect)

    def test_multiple_status_effects_stacked(self, base_character):
        """Multiple status effects should all be applied."""
        base_character.status_effects = [
            {"name": "Blessed", "modifier": 2},
            {"name": "Weakened", "modifier": -1},
        ]
        result = _calculate_modifier(base_character, ActionType.STRENGTH)
        assert result == 1  # 0 + 2 - 1

    def test_status_effect_string_ignored(self, base_character):
        """String status effects (legacy format) should not affect modifier."""
        base_character.status_effects = ["Blessed", "Inspired"]
        result = _calculate_modifier(base_character, ActionType.STRENGTH)
        assert result == 0  # No change from base

    def test_status_effect_dict_without_modifier_key(self, base_character):
        """A dict status effect missing the 'modifier' key adds 0."""
        base_character.status_effects = [{"name": "Haste", "duration": 3}]
        result = _calculate_modifier(base_character, ActionType.STRENGTH)
        assert result == 0

    def test_status_effect_non_int_modifier_ignored(self, base_character):
        """A status effect with a non-integer modifier should not be applied."""
        base_character.status_effects = [{"name": "Strange", "modifier": "two"}]
        result = _calculate_modifier(base_character, ActionType.STRENGTH)
        assert result == 0

    def test_mixed_string_and_dict_status_effects(self, base_character):
        """Only dict effects with int modifiers should contribute."""
        base_character.status_effects = [
            "Blessed",
            {"name": "Strong", "modifier": 3},
            {"name": "NoMod"},
            "Inspired",
            {"name": "Weakened", "modifier": -1},
        ]
        result = _calculate_modifier(base_character, ActionType.STRENGTH)
        assert result == 2  # 0 + 3 - 1

    # -- Combined: ability + skill + status effect ---------------------------

    def test_combined_modifier(self, skilled_character):
        """
        Skilled Fighter: STR=18 -> (18-10)//2 = 4
        Skill: Athletics (ability=strength) -> +2
        Status: Blessed (modifier=+2) -> +2
        Total: 4 + 2 + 2 = 8
        """
        result = _calculate_modifier(skilled_character, ActionType.STRENGTH)
        assert result == 8

    def test_combined_modifier_different_ability(self, skilled_character):
        """
        Skilled Fighter: DEX=14 -> (14-10)//2 = 2
        Skill: Stealth (ability=dexterity) -> +2
        Status: Blessed (modifier=+2) -> +2
        Total: 2 + 2 + 2 = 6
        """
        result = _calculate_modifier(skilled_character, ActionType.DEXTERITY)
        assert result == 6

    def test_combined_no_matching_skill(self, skilled_character):
        """
        Skilled Fighter: INT=8 -> (8-10)//2 = -1
        No skill matches intelligence -> +0
        Status: Blessed (modifier=+2) -> +2
        Total: -1 + 0 + 2 = 1
        """
        result = _calculate_modifier(skilled_character, ActionType.INTELLIGENCE)
        assert result == 1


# ===========================================================================
# _parse_dc_response tests
# ===========================================================================


class TestParseDcResponse:
    """Tests for _parse_dc_response."""

    def test_valid_json_array(self):
        """A plain JSON array should be parsed correctly."""
        response = json.dumps([
            {
                "character_id": 1,
                "action_type": "strength",
                "difficulty": 12,
                "reasoning": "The door is old and weak.",
            }
        ])
        result = _parse_dc_response(response)
        assert result[1]["difficulty"] == 12
        assert result[1]["reasoning"] == "The door is old and weak."

    def test_json_wrapped_in_markdown_code_block(self):
        """Response wrapped in ```json ... ``` should be parsed correctly."""
        inner = json.dumps([
            {
                "character_id": 1,
                "difficulty": 18,
                "reasoning": "Very hard lock.",
            }
        ])
        response = f"```json\n{inner}\n```"
        result = _parse_dc_response(response)
        assert result[1]["difficulty"] == 18
        assert result[1]["reasoning"] == "Very hard lock."

    def test_json_wrapped_in_plain_code_block(self):
        """Response wrapped in ``` ... ``` (no language tag) should work."""
        inner = json.dumps([
            {
                "character_id": 3,
                "difficulty": 10,
                "reasoning": "Easy task.",
            }
        ])
        response = f"```\n{inner}\n```"
        result = _parse_dc_response(response)
        assert result[3]["difficulty"] == 10

    def test_missing_json_array_returns_empty(self):
        """If no JSON array is found, return empty dict."""
        result = _parse_dc_response("I think the difficulty should be 15.")
        assert result == {}

    def test_invalid_json_returns_empty(self):
        """Malformed JSON should return empty dict without raising."""
        result = _parse_dc_response('[{"character_id": 1, "difficulty": }]')
        assert result == {}

    def test_empty_string_returns_empty(self):
        """Empty string should return empty dict."""
        result = _parse_dc_response("")
        assert result == {}

    def test_multiple_characters_mapped_by_id(self):
        """Multiple characters should be keyed by character_id."""
        response = json.dumps([
            {"character_id": 1, "difficulty": 12, "reasoning": "Reason A"},
            {"character_id": 2, "difficulty": 20, "reasoning": "Reason B"},
        ])
        result = _parse_dc_response(response)
        assert len(result) == 2
        assert result[1]["difficulty"] == 12
        assert result[2]["difficulty"] == 20

    def test_difficulty_reasoning_field_fallback_to_reasoning(self):
        """
        When the AI uses 'difficulty_reasoning' instead of 'reasoning',
        the value should still be available under the 'reasoning' key.
        """
        response = json.dumps([
            {
                "character_id": 1,
                "difficulty": 15,
                "difficulty_reasoning": "Explained via difficulty_reasoning field.",
            }
        ])
        result = _parse_dc_response(response)
        assert result[1]["reasoning"] == "Explained via difficulty_reasoning field."

    def test_reasoning_takes_priority_over_difficulty_reasoning(self):
        """
        When both 'reasoning' and 'difficulty_reasoning' are present,
        'reasoning' should take priority (because of `or` short-circuit).
        """
        response = json.dumps([
            {
                "character_id": 1,
                "difficulty": 15,
                "reasoning": "Primary reasoning.",
                "difficulty_reasoning": "Fallback reasoning.",
            }
        ])
        result = _parse_dc_response(response)
        assert result[1]["reasoning"] == "Primary reasoning."

    def test_default_difficulty_when_missing(self):
        """If 'difficulty' key is missing, default to 15."""
        response = json.dumps([
            {"character_id": 1, "reasoning": "Some reasoning."}
        ])
        result = _parse_dc_response(response)
        assert result[1]["difficulty"] == 15

    def test_entry_without_character_id_skipped(self):
        """Entries missing 'character_id' should be skipped."""
        response = json.dumps([
            {"difficulty": 15, "reasoning": "No character ID"},
            {"character_id": 2, "difficulty": 10, "reasoning": "Valid"},
        ])
        result = _parse_dc_response(response)
        assert len(result) == 1
        assert 2 in result

    def test_text_before_and_after_json(self):
        """Surrounding text should be stripped, JSON array extracted."""
        response = (
            'Here is my analysis:\n\n'
            '[{"character_id": 1, "difficulty": 14, "reasoning": "Analysis"}]\n\n'
            'Let me know if you need more details.'
        )
        result = _parse_dc_response(response)
        assert result[1]["difficulty"] == 14


# ===========================================================================
# analyze_and_judge_actions tests (with AI mocked)
# ===========================================================================


class TestAnalyzeAndJudgeActions:
    """Tests for analyze_and_judge_actions with mocked AI."""

    def _make_ai_response(self, entries: list[dict]) -> MagicMock:
        """Helper to build a mock AI response object."""
        mock_response = MagicMock()
        mock_response.content = json.dumps(entries)
        return mock_response

    @pytest.mark.asyncio
    async def test_basic_analysis_with_modifier(self, sample_characters, sample_actions):
        """Modifier should be calculated from character ability scores."""
        ai_entries = [
            {"character_id": 1, "difficulty": 15, "reasoning": "Moderate"},
            {"character_id": 2, "difficulty": 15, "reasoning": "Moderate"},
        ]

        with patch(
            "app.services.ai_nodes.judgment_node._determine_difficulty_with_ai",
            new_callable=AsyncMock,
            return_value={
                1: {"difficulty": 15, "reasoning": "Moderate"},
                2: {"difficulty": 15, "reasoning": "Moderate"},
            },
        ):
            results = await analyze_and_judge_actions(
                player_actions=sample_actions,
                characters=sample_characters,
                world_context="A fantasy world.",
                story_history=[],
            )

        assert len(results) == 2

        # Warrior: STR 16 -> (16-10)//2 = 3, skill Athletics +2 = 5
        warrior = next(r for r in results if r.character_id == 1)
        assert warrior.modifier == 5

        # Rogue: DEX 18 -> (18-10)//2 = 4, skill Stealth +2 = 6
        rogue = next(r for r in results if r.character_id == 2)
        assert rogue.modifier == 6

    @pytest.mark.asyncio
    async def test_dc_from_ai_applied(self, sample_characters, sample_actions):
        """DC values from AI should be applied to the analysis results."""
        with patch(
            "app.services.ai_nodes.judgment_node._determine_difficulty_with_ai",
            new_callable=AsyncMock,
            return_value={
                1: {"difficulty": 12, "reasoning": "Old door"},
                2: {"difficulty": 18, "reasoning": "Alert guards"},
            },
        ):
            results = await analyze_and_judge_actions(
                player_actions=sample_actions,
                characters=sample_characters,
                world_context="A fantasy world.",
                story_history=[],
            )

        warrior = next(r for r in results if r.character_id == 1)
        assert warrior.difficulty == 12
        assert warrior.difficulty_reasoning == "Old door"

        rogue = next(r for r in results if r.character_id == 2)
        assert rogue.difficulty == 18
        assert rogue.difficulty_reasoning == "Alert guards"

    @pytest.mark.asyncio
    async def test_dc_clamped_to_minimum_5(self, sample_characters):
        """DC below 5 should be clamped to 5."""
        actions = [
            PlayerAction(character_id=1, action_text="Breathe", action_type=ActionType.STRENGTH),
        ]

        with patch(
            "app.services.ai_nodes.judgment_node._determine_difficulty_with_ai",
            new_callable=AsyncMock,
            return_value={
                1: {"difficulty": 2, "reasoning": "Trivial"},
            },
        ):
            results = await analyze_and_judge_actions(
                player_actions=actions,
                characters=sample_characters,
                world_context="",
                story_history=[],
            )

        assert results[0].difficulty == 5

    @pytest.mark.asyncio
    async def test_dc_clamped_to_maximum_30(self, sample_characters):
        """DC above 30 should be clamped to 30 (before soft-cap)."""
        # Give character a very high modifier so soft-cap doesn't reduce further
        char = sample_characters[0]
        char.strength = 30  # modifier base = 10
        char.skills = [{"name": "Godlike", "ability": "strength"}]  # +2 = 12
        char.status_effects = [{"name": "Divine", "modifier": 10}]  # total = 22

        actions = [
            PlayerAction(character_id=1, action_text="Destroy mountain", action_type=ActionType.STRENGTH),
        ]

        with patch(
            "app.services.ai_nodes.judgment_node._determine_difficulty_with_ai",
            new_callable=AsyncMock,
            return_value={
                1: {"difficulty": 50, "reasoning": "Impossible"},
            },
        ):
            results = await analyze_and_judge_actions(
                player_actions=actions,
                characters=sample_characters,
                world_context="",
                story_history=[],
            )

        assert results[0].difficulty == 30

    @pytest.mark.asyncio
    async def test_dc_soft_cap_applied(self, sample_characters):
        """
        DC soft-cap: if DC > modifier + 18 and DC > 20, cap to max(20, modifier + 18).

        Warrior: STR=16, skill=+2 -> modifier = 3 + 2 = 5
        max_reasonable_dc = 5 + 18 = 23
        DC=28 is > 23 and > 20, so should be capped to max(20, 23) = 23.
        """
        actions = [
            PlayerAction(character_id=1, action_text="Lift the world", action_type=ActionType.STRENGTH),
        ]

        with patch(
            "app.services.ai_nodes.judgment_node._determine_difficulty_with_ai",
            new_callable=AsyncMock,
            return_value={
                1: {"difficulty": 28, "reasoning": "Nearly impossible"},
            },
        ):
            results = await analyze_and_judge_actions(
                player_actions=actions,
                characters=sample_characters,
                world_context="",
                story_history=[],
            )

        assert results[0].difficulty == 23

    @pytest.mark.asyncio
    async def test_dc_soft_cap_not_applied_when_dc_lte_20(self, sample_characters):
        """
        DC soft-cap should NOT apply if DC <= 20, even if DC > modifier + 18.

        Low-modifier character with DC=20 should keep DC=20.
        """
        # Make character with very low modifier
        char = sample_characters[0]
        char.strength = 1  # modifier = -5
        char.skills = []
        char.status_effects = []
        # max_reasonable_dc = -5 + 18 = 13
        # DC=20 > 13 but DC is NOT > 20, so soft-cap should not apply

        actions = [
            PlayerAction(character_id=1, action_text="Lift something heavy", action_type=ActionType.STRENGTH),
        ]

        with patch(
            "app.services.ai_nodes.judgment_node._determine_difficulty_with_ai",
            new_callable=AsyncMock,
            return_value={
                1: {"difficulty": 20, "reasoning": "Hard task"},
            },
        ):
            results = await analyze_and_judge_actions(
                player_actions=actions,
                characters=sample_characters,
                world_context="",
                story_history=[],
            )

        assert results[0].difficulty == 20

    @pytest.mark.asyncio
    async def test_dc_soft_cap_floors_at_20(self, sample_characters):
        """
        When modifier + 18 < 20, soft-cap should floor at 20 (not go lower).

        Character with modifier=-3: max_reasonable_dc = -3 + 18 = 15
        DC=25 > 15 and > 20. Soft-cap: min(25, max(20, 15)) = 20.
        """
        char = sample_characters[0]
        char.strength = 4  # (4-10)//2 = -3
        char.skills = []
        char.status_effects = []

        actions = [
            PlayerAction(character_id=1, action_text="Move the boulder", action_type=ActionType.STRENGTH),
        ]

        with patch(
            "app.services.ai_nodes.judgment_node._determine_difficulty_with_ai",
            new_callable=AsyncMock,
            return_value={
                1: {"difficulty": 25, "reasoning": "Very hard"},
            },
        ):
            results = await analyze_and_judge_actions(
                player_actions=actions,
                characters=sample_characters,
                world_context="",
                story_history=[],
            )

        assert results[0].difficulty == 20

    @pytest.mark.asyncio
    async def test_fallback_dc_15_when_ai_fails(self, sample_characters, sample_actions):
        """When AI raises an exception, all DCs should fall back to 15."""
        with patch(
            "app.services.ai_nodes.judgment_node._determine_difficulty_with_ai",
            new_callable=AsyncMock,
            side_effect=ValueError("API rate limit exceeded"),
        ):
            results = await analyze_and_judge_actions(
                player_actions=sample_actions,
                characters=sample_characters,
                world_context="",
                story_history=[],
            )

        assert len(results) == 2
        for r in results:
            assert r.difficulty == 15
            assert "AI" in r.difficulty_reasoning or "오류" in r.difficulty_reasoning

    @pytest.mark.asyncio
    async def test_empty_actions_raises_value_error(self, sample_characters):
        """An empty action list should raise ValueError."""
        with pytest.raises(ValueError, match="No valid actions to analyze"):
            await analyze_and_judge_actions(
                player_actions=[],
                characters=sample_characters,
                world_context="",
                story_history=[],
            )

    @pytest.mark.asyncio
    async def test_actions_with_unknown_character_skipped(self, sample_characters):
        """Actions whose character_id is not in characters list are skipped."""
        actions = [
            PlayerAction(character_id=999, action_text="Do something", action_type=ActionType.STRENGTH),
        ]

        with pytest.raises(ValueError, match="No valid actions to analyze"):
            await analyze_and_judge_actions(
                player_actions=actions,
                characters=sample_characters,
                world_context="",
                story_history=[],
            )

    @pytest.mark.asyncio
    async def test_partial_unknown_characters(self, sample_characters):
        """
        Only actions with known characters should be included in the result.
        Unknown characters are silently skipped.
        """
        actions = [
            PlayerAction(character_id=1, action_text="Attack", action_type=ActionType.STRENGTH),
            PlayerAction(character_id=999, action_text="Ghost action", action_type=ActionType.WISDOM),
        ]

        with patch(
            "app.services.ai_nodes.judgment_node._determine_difficulty_with_ai",
            new_callable=AsyncMock,
            return_value={
                1: {"difficulty": 15, "reasoning": "Normal"},
            },
        ):
            results = await analyze_and_judge_actions(
                player_actions=actions,
                characters=sample_characters,
                world_context="",
                story_history=[],
            )

        assert len(results) == 1
        assert results[0].character_id == 1

    @pytest.mark.asyncio
    async def test_action_text_preserved(self, sample_characters):
        """The action_text should be passed through to the analysis result."""
        actions = [
            PlayerAction(character_id=1, action_text="I leap across the chasm!", action_type=ActionType.DEXTERITY),
        ]

        with patch(
            "app.services.ai_nodes.judgment_node._determine_difficulty_with_ai",
            new_callable=AsyncMock,
            return_value={
                1: {"difficulty": 15, "reasoning": "Normal"},
            },
        ):
            results = await analyze_and_judge_actions(
                player_actions=actions,
                characters=sample_characters,
                world_context="",
                story_history=[],
            )

        assert results[0].action_text == "I leap across the chasm!"
        assert results[0].action_type == ActionType.DEXTERITY

    @pytest.mark.asyncio
    async def test_default_reasoning_when_ai_has_no_entry(self, sample_characters):
        """When AI returns no entry for a character, default reasoning is applied."""
        actions = [
            PlayerAction(character_id=1, action_text="Attack", action_type=ActionType.STRENGTH),
        ]

        with patch(
            "app.services.ai_nodes.judgment_node._determine_difficulty_with_ai",
            new_callable=AsyncMock,
            return_value={},  # No entries at all
        ):
            results = await analyze_and_judge_actions(
                player_actions=actions,
                characters=sample_characters,
                world_context="",
                story_history=[],
            )

        assert results[0].difficulty == 15
        assert "기본 난이도" in results[0].difficulty_reasoning

    @pytest.mark.asyncio
    async def test_result_types_are_action_analysis(self, sample_characters, sample_actions):
        """All returned results should be ActionAnalysis instances."""
        with patch(
            "app.services.ai_nodes.judgment_node._determine_difficulty_with_ai",
            new_callable=AsyncMock,
            return_value={
                1: {"difficulty": 15, "reasoning": "Normal"},
                2: {"difficulty": 15, "reasoning": "Normal"},
            },
        ):
            results = await analyze_and_judge_actions(
                player_actions=sample_actions,
                characters=sample_characters,
                world_context="",
                story_history=[],
            )

        for r in results:
            assert isinstance(r, ActionAnalysis)
