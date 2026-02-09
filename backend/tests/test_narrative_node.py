"""
Tests for the narrative generation node module.

Tests cover the _get_outcome_korean helper, the generate_narrative function,
and the generate_narrative_streaming async generator.
All AI/LLM calls are mocked via unittest.mock.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas import CharacterSheet, JudgmentOutcome, JudgmentResult
from app.services.ai_nodes.narrative_node import (
    _get_outcome_korean,
    generate_narrative,
    generate_narrative_streaming,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_characters() -> list[CharacterSheet]:
    """Create a list of sample characters for testing."""
    return [
        CharacterSheet(
            id=1,
            name="Ella",
            race="Human",
            concept="Brave warrior",
            strength=18,
            dexterity=14,
            constitution=12,
            intelligence=10,
            wisdom=10,
            charisma=10,
            skills=[],
            weaknesses=[],
            status_effects=[],
        ),
        CharacterSheet(
            id=2,
            name="Kael",
            race="Elf",
            concept="Shadow rogue",
            strength=10,
            dexterity=18,
            constitution=10,
            intelligence=12,
            wisdom=14,
            charisma=10,
            skills=[],
            weaknesses=[],
            status_effects=[],
        ),
    ]


@pytest.fixture
def sample_judgments() -> list[JudgmentResult]:
    """Create a list of sample judgment results for testing."""
    return [
        JudgmentResult(
            character_id=1,
            action_text="Swing sword at the goblin",
            dice_result=15,
            modifier=4,
            final_value=19,
            difficulty=12,
            difficulty_reasoning="A basic melee attack",
            outcome=JudgmentOutcome.SUCCESS,
            outcome_reasoning="The attack lands solidly.",
        ),
        JudgmentResult(
            character_id=2,
            action_text="Sneak behind the enemy",
            dice_result=20,
            modifier=4,
            final_value=24,
            difficulty=15,
            difficulty_reasoning="Sneaking in dim light",
            outcome=JudgmentOutcome.CRITICAL_SUCCESS,
            outcome_reasoning="A perfect stealth maneuver!",
        ),
    ]


@pytest.fixture
def single_judgment_success() -> list[JudgmentResult]:
    """A single SUCCESS judgment."""
    return [
        JudgmentResult(
            character_id=1,
            action_text="Open the door",
            dice_result=12,
            modifier=2,
            final_value=14,
            difficulty=10,
            difficulty_reasoning="Simple lock",
            outcome=JudgmentOutcome.SUCCESS,
            outcome_reasoning="The door opens.",
        ),
    ]


@pytest.fixture
def world_context() -> str:
    return "A dark medieval fantasy world filled with monsters and magic."


@pytest.fixture
def story_history() -> list[str]:
    return [
        "The party entered the dark cave.",
        "Strange sounds echoed from the depths.",
    ]


# ---------------------------------------------------------------------------
# Tests for _get_outcome_korean
# ---------------------------------------------------------------------------


class TestGetOutcomeKorean:
    """Tests for the _get_outcome_korean helper function."""

    def test_critical_success(self):
        """CRITICAL_SUCCESS maps to '대성공'."""
        assert _get_outcome_korean("critical_success") == "대성공"

    def test_success(self):
        """SUCCESS maps to '성공'."""
        assert _get_outcome_korean("success") == "성공"

    def test_failure(self):
        """FAILURE maps to '실패'."""
        assert _get_outcome_korean("failure") == "실패"

    def test_critical_failure(self):
        """CRITICAL_FAILURE maps to '대실패'."""
        assert _get_outcome_korean("critical_failure") == "대실패"

    def test_unknown_outcome_returns_input(self):
        """An unrecognized outcome string is returned as-is."""
        assert _get_outcome_korean("unknown_thing") == "unknown_thing"

    def test_empty_string_returns_empty(self):
        """An empty string input is returned as-is."""
        assert _get_outcome_korean("") == ""

    def test_all_enum_values_have_korean(self):
        """Every JudgmentOutcome enum value has a Korean translation."""
        for outcome in JudgmentOutcome:
            result = _get_outcome_korean(outcome.value)
            # Should never fall back to the raw enum value
            assert result != outcome.value


# ---------------------------------------------------------------------------
# Tests for generate_narrative
# ---------------------------------------------------------------------------


class TestGenerateNarrative:
    """Tests for the generate_narrative async function."""

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_returns_narrative_text(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
        story_history,
    ):
        """generate_narrative should return a stripped narrative string."""
        # Arrange
        mock_load_prompt.return_value = MagicMock(content="System prompt text")

        mock_response = MagicMock()
        mock_response.content = "  The sword gleams in the moonlight.  "

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_response)

        # Patch the chain composition (template | llm) to return our mock chain
        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            # Act
            result = await generate_narrative(
                judgments=sample_judgments,
                characters=sample_characters,
                world_context=world_context,
                story_history=story_history,
                llm_model="gpt-4o",
            )

        # Assert
        assert isinstance(result, str)
        assert result == "The sword gleams in the moonlight."

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_prompt_includes_judgment_details(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
        story_history,
    ):
        """The context passed to the chain should contain judgment information."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        captured_context = {}

        async def capture_invoke(input_dict):
            captured_context.update(input_dict)
            resp = MagicMock()
            resp.content = "narrative text"
            return resp

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(side_effect=capture_invoke)

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            await generate_narrative(
                judgments=sample_judgments,
                characters=sample_characters,
                world_context=world_context,
                story_history=story_history,
            )

        context = captured_context["context"]

        # Verify judgment details are in the context
        assert "Swing sword at the goblin" in context
        assert "Sneak behind the enemy" in context
        assert "Ella" in context
        assert "Kael" in context
        assert "성공" in context  # Korean for success
        assert "대성공" in context  # Korean for critical success

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_prompt_includes_world_context(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
        story_history,
    ):
        """The context should include the world context."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        captured_context = {}

        async def capture_invoke(input_dict):
            captured_context.update(input_dict)
            resp = MagicMock()
            resp.content = "narrative"
            return resp

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(side_effect=capture_invoke)

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            await generate_narrative(
                judgments=sample_judgments,
                characters=sample_characters,
                world_context=world_context,
                story_history=story_history,
            )

        context = captured_context["context"]
        assert "dark medieval fantasy world" in context

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_prompt_includes_story_history(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
        story_history,
    ):
        """The context should include recent story history entries."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        captured_context = {}

        async def capture_invoke(input_dict):
            captured_context.update(input_dict)
            resp = MagicMock()
            resp.content = "narrative"
            return resp

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(side_effect=capture_invoke)

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            await generate_narrative(
                judgments=sample_judgments,
                characters=sample_characters,
                world_context=world_context,
                story_history=story_history,
            )

        context = captured_context["context"]
        assert "The party entered the dark cave." in context
        assert "Strange sounds echoed from the depths." in context

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_story_history_limited_to_5(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
    ):
        """Only the last 5 story history entries should be included."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        long_history = [f"Entry {i}" for i in range(10)]
        captured_context = {}

        async def capture_invoke(input_dict):
            captured_context.update(input_dict)
            resp = MagicMock()
            resp.content = "narrative"
            return resp

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(side_effect=capture_invoke)

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            await generate_narrative(
                judgments=sample_judgments,
                characters=sample_characters,
                world_context=world_context,
                story_history=long_history,
            )

        context = captured_context["context"]

        # First 5 entries (0-4) should NOT be included
        for i in range(5):
            assert f"Entry {i}" not in context

        # Last 5 entries (5-9) should be included
        for i in range(5, 10):
            assert f"Entry {i}" in context

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_story_history_with_content_attribute(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
    ):
        """Story history entries with a .content attribute should use that."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        entry = SimpleNamespace(content="Entry from StoryLogEntry object")
        captured_context = {}

        async def capture_invoke(input_dict):
            captured_context.update(input_dict)
            resp = MagicMock()
            resp.content = "narrative"
            return resp

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(side_effect=capture_invoke)

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            await generate_narrative(
                judgments=sample_judgments,
                characters=sample_characters,
                world_context=world_context,
                story_history=[entry],
            )

        context = captured_context["context"]
        assert "Entry from StoryLogEntry object" in context

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_empty_world_context_excluded(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
    ):
        """When world_context is empty, it should not appear in context."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        captured_context = {}

        async def capture_invoke(input_dict):
            captured_context.update(input_dict)
            resp = MagicMock()
            resp.content = "narrative"
            return resp

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(side_effect=capture_invoke)

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            await generate_narrative(
                judgments=sample_judgments,
                characters=sample_characters,
                world_context="",
                story_history=[],
            )

        context = captured_context["context"]
        # The world context section header should not appear
        assert "## 세계관" not in context

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_empty_story_history_excluded(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
    ):
        """When story_history is empty, it should not appear in context."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        captured_context = {}

        async def capture_invoke(input_dict):
            captured_context.update(input_dict)
            resp = MagicMock()
            resp.content = "narrative"
            return resp

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(side_effect=capture_invoke)

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            await generate_narrative(
                judgments=sample_judgments,
                characters=sample_characters,
                world_context=world_context,
                story_history=[],
            )

        context = captured_context["context"]
        assert "## 최근 스토리" not in context

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_character_race_and_concept_in_context(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
    ):
        """Character race and concept should appear in the context."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        captured_context = {}

        async def capture_invoke(input_dict):
            captured_context.update(input_dict)
            resp = MagicMock()
            resp.content = "narrative"
            return resp

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(side_effect=capture_invoke)

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            await generate_narrative(
                judgments=sample_judgments,
                characters=sample_characters,
                world_context=world_context,
                story_history=[],
            )

        context = captured_context["context"]
        assert "Human" in context
        assert "Brave warrior" in context
        assert "Elf" in context
        assert "Shadow rogue" in context

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_unknown_character_id_uses_fallback_name(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_characters,
        world_context,
    ):
        """When a judgment references an unknown character_id, use a fallback name."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        judgment_with_unknown_char = JudgmentResult(
            character_id=999,
            action_text="Do something",
            dice_result=10,
            modifier=0,
            final_value=10,
            difficulty=10,
            outcome=JudgmentOutcome.SUCCESS,
            outcome_reasoning="It works.",
        )

        captured_context = {}

        async def capture_invoke(input_dict):
            captured_context.update(input_dict)
            resp = MagicMock()
            resp.content = "narrative"
            return resp

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(side_effect=capture_invoke)

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            await generate_narrative(
                judgments=[judgment_with_unknown_char],
                characters=sample_characters,
                world_context=world_context,
                story_history=[],
            )

        context = captured_context["context"]
        assert "캐릭터 999" in context

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_all_four_outcomes_in_context(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_characters,
        world_context,
    ):
        """All four outcome types should be properly converted to Korean in context."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        judgments = [
            JudgmentResult(
                character_id=1,
                action_text="Action CS",
                dice_result=20,
                modifier=0,
                final_value=20,
                difficulty=10,
                outcome=JudgmentOutcome.CRITICAL_SUCCESS,
                outcome_reasoning="Perfect!",
            ),
            JudgmentResult(
                character_id=1,
                action_text="Action S",
                dice_result=15,
                modifier=0,
                final_value=15,
                difficulty=10,
                outcome=JudgmentOutcome.SUCCESS,
                outcome_reasoning="Good.",
            ),
            JudgmentResult(
                character_id=1,
                action_text="Action F",
                dice_result=5,
                modifier=0,
                final_value=5,
                difficulty=10,
                outcome=JudgmentOutcome.FAILURE,
                outcome_reasoning="Missed.",
            ),
            JudgmentResult(
                character_id=1,
                action_text="Action CF",
                dice_result=1,
                modifier=0,
                final_value=1,
                difficulty=10,
                outcome=JudgmentOutcome.CRITICAL_FAILURE,
                outcome_reasoning="Terrible!",
            ),
        ]

        captured_context = {}

        async def capture_invoke(input_dict):
            captured_context.update(input_dict)
            resp = MagicMock()
            resp.content = "narrative"
            return resp

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(side_effect=capture_invoke)

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            await generate_narrative(
                judgments=judgments,
                characters=sample_characters,
                world_context=world_context,
                story_history=[],
            )

        context = captured_context["context"]
        assert "대성공" in context
        assert "성공" in context
        assert "실패" in context
        assert "대실패" in context

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_modifier_formatted_with_sign(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_characters,
        world_context,
    ):
        """Modifier values should be formatted with a +/- sign."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        judgments = [
            JudgmentResult(
                character_id=1,
                action_text="Test action",
                dice_result=10,
                modifier=3,
                final_value=13,
                difficulty=10,
                outcome=JudgmentOutcome.SUCCESS,
                outcome_reasoning="ok",
            ),
        ]

        captured_context = {}

        async def capture_invoke(input_dict):
            captured_context.update(input_dict)
            resp = MagicMock()
            resp.content = "narrative"
            return resp

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(side_effect=capture_invoke)

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            await generate_narrative(
                judgments=judgments,
                characters=sample_characters,
                world_context=world_context,
                story_history=[],
            )

        context = captured_context["context"]
        assert "+3" in context

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_negative_modifier_formatted(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_characters,
        world_context,
    ):
        """Negative modifier values should be formatted with a minus sign."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        judgments = [
            JudgmentResult(
                character_id=1,
                action_text="Test action",
                dice_result=10,
                modifier=-2,
                final_value=8,
                difficulty=10,
                outcome=JudgmentOutcome.FAILURE,
                outcome_reasoning="nope",
            ),
        ]

        captured_context = {}

        async def capture_invoke(input_dict):
            captured_context.update(input_dict)
            resp = MagicMock()
            resp.content = "narrative"
            return resp

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(side_effect=capture_invoke)

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            await generate_narrative(
                judgments=judgments,
                characters=sample_characters,
                world_context=world_context,
                story_history=[],
            )

        context = captured_context["context"]
        assert "-2" in context

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_ai_call_failure_raises_value_error(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
        story_history,
    ):
        """When the AI chain raises an exception, a ValueError should be raised."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(
            side_effect=RuntimeError("API connection failed")
        )

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            with pytest.raises(ValueError, match="서술 생성 실패"):
                await generate_narrative(
                    judgments=sample_judgments,
                    characters=sample_characters,
                    world_context=world_context,
                    story_history=story_history,
                )

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_ai_error_preserves_cause(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
        story_history,
    ):
        """The ValueError raised on AI failure should chain the original exception."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")
        original_error = RuntimeError("timeout")

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(side_effect=original_error)

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            with pytest.raises(ValueError) as exc_info:
                await generate_narrative(
                    judgments=sample_judgments,
                    characters=sample_characters,
                    world_context=world_context,
                    story_history=story_history,
                )

            assert exc_info.value.__cause__ is original_error

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_llm_model_parameter_passed(
        self,
        mock_load_prompt,
        mock_llm_cls,
        single_judgment_success,
        sample_characters,
        world_context,
    ):
        """The llm_model parameter should be passed to ChatLiteLLM."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        mock_response = MagicMock()
        mock_response.content = "narrative"

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_response)

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            await generate_narrative(
                judgments=single_judgment_success,
                characters=sample_characters,
                world_context=world_context,
                story_history=[],
                llm_model="gpt-4-turbo",
            )

        mock_llm_cls.assert_called_once_with(
            model="gpt-4-turbo",
            temperature=1.0,
            max_tokens=4000,
        )

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_character_without_race_and_concept(
        self,
        mock_load_prompt,
        mock_llm_cls,
        single_judgment_success,
        world_context,
    ):
        """Characters without race/concept should not include those lines."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        minimal_character = CharacterSheet(id=1, name="Nobody")
        captured_context = {}

        async def capture_invoke(input_dict):
            captured_context.update(input_dict)
            resp = MagicMock()
            resp.content = "narrative"
            return resp

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(side_effect=capture_invoke)

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            await generate_narrative(
                judgments=single_judgment_success,
                characters=[minimal_character],
                world_context=world_context,
                story_history=[],
            )

        context = captured_context["context"]
        assert "Nobody" in context
        # The race/concept lines should not be present for this character
        assert "종족" not in context
        assert "컨셉" not in context


# ---------------------------------------------------------------------------
# Tests for generate_narrative_streaming
# ---------------------------------------------------------------------------


class TestGenerateNarrativeStreaming:
    """Tests for the generate_narrative_streaming async generator."""

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_yields_tokens(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
        story_history,
    ):
        """Streaming should yield individual tokens from the LLM."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        chunks = [
            MagicMock(content="Hello"),
            MagicMock(content=" world"),
            MagicMock(content="!"),
        ]

        async def mock_astream(input_dict):
            for chunk in chunks:
                yield chunk

        mock_chain = MagicMock()
        mock_chain.astream = mock_astream

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            tokens = []
            async for token in generate_narrative_streaming(
                judgments=sample_judgments,
                characters=sample_characters,
                world_context=world_context,
                story_history=story_history,
            ):
                tokens.append(token)

        assert tokens == ["Hello", " world", "!"]

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_yields_correct_order(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
        story_history,
    ):
        """Tokens should be yielded in the exact order the LLM produces them."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        token_sequence = ["A", "B", "C", "D", "E"]
        chunks = [MagicMock(content=t) for t in token_sequence]

        async def mock_astream(input_dict):
            for chunk in chunks:
                yield chunk

        mock_chain = MagicMock()
        mock_chain.astream = mock_astream

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            tokens = []
            async for token in generate_narrative_streaming(
                judgments=sample_judgments,
                characters=sample_characters,
                world_context=world_context,
                story_history=story_history,
            ):
                tokens.append(token)

        assert tokens == token_sequence

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_empty_content_chunks_skipped(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
        story_history,
    ):
        """Chunks with empty or missing content should be skipped."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        chunks = [
            MagicMock(content="Hello"),
            MagicMock(content=""),
            MagicMock(content="World"),
            MagicMock(spec=[]),  # no content attribute
        ]

        async def mock_astream(input_dict):
            for chunk in chunks:
                yield chunk

        mock_chain = MagicMock()
        mock_chain.astream = mock_astream

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            tokens = []
            async for token in generate_narrative_streaming(
                judgments=sample_judgments,
                characters=sample_characters,
                world_context=world_context,
                story_history=story_history,
            ):
                tokens.append(token)

        assert tokens == ["Hello", "World"]

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_no_tokens_produced(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
        story_history,
    ):
        """When the LLM produces no chunks, no tokens should be yielded."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        async def mock_astream(input_dict):
            return
            yield  # make it an async generator

        mock_chain = MagicMock()
        mock_chain.astream = mock_astream

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            tokens = []
            async for token in generate_narrative_streaming(
                judgments=sample_judgments,
                characters=sample_characters,
                world_context=world_context,
                story_history=story_history,
            ):
                tokens.append(token)

        assert tokens == []

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_streaming_failure_raises_value_error(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
        story_history,
    ):
        """When the streaming chain raises an error, a ValueError should be raised."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        async def mock_astream_error(input_dict):
            yield MagicMock(content="partial")
            raise RuntimeError("Stream interrupted")

        mock_chain = MagicMock()
        mock_chain.astream = mock_astream_error

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            with pytest.raises(ValueError, match="서술 스트리밍 실패"):
                tokens = []
                async for token in generate_narrative_streaming(
                    judgments=sample_judgments,
                    characters=sample_characters,
                    world_context=world_context,
                    story_history=story_history,
                ):
                    tokens.append(token)

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_streaming_error_preserves_cause(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
        story_history,
    ):
        """The ValueError raised on streaming failure should chain the original exception."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")
        original_error = ConnectionError("lost connection")

        async def mock_astream_error(input_dict):
            raise original_error
            yield  # noqa: RUF027 - make this an async generator

        mock_chain = MagicMock()
        mock_chain.astream = mock_astream_error

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            with pytest.raises(ValueError) as exc_info:
                async for _ in generate_narrative_streaming(
                    judgments=sample_judgments,
                    characters=sample_characters,
                    world_context=world_context,
                    story_history=story_history,
                ):
                    pass

            assert exc_info.value.__cause__ is original_error

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_streaming_default_model(
        self,
        mock_load_prompt,
        mock_llm_cls,
        single_judgment_success,
        sample_characters,
        world_context,
    ):
        """The default llm_model for streaming should be 'gemini/gemini-3-pro-preview'."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        async def mock_astream(input_dict):
            yield MagicMock(content="token")

        mock_chain = MagicMock()
        mock_chain.astream = mock_astream

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            async for _ in generate_narrative_streaming(
                judgments=single_judgment_success,
                characters=sample_characters,
                world_context=world_context,
                story_history=[],
            ):
                pass

        mock_llm_cls.assert_called_once_with(
            model="gemini/gemini-3-pro-preview",
            temperature=1.0,
            max_tokens=4000,
        )

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_streaming_custom_model(
        self,
        mock_load_prompt,
        mock_llm_cls,
        single_judgment_success,
        sample_characters,
        world_context,
    ):
        """A custom llm_model should be passed to ChatLiteLLM."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        async def mock_astream(input_dict):
            yield MagicMock(content="token")

        mock_chain = MagicMock()
        mock_chain.astream = mock_astream

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            async for _ in generate_narrative_streaming(
                judgments=single_judgment_success,
                characters=sample_characters,
                world_context=world_context,
                story_history=[],
                llm_model="claude-opus-4-20250514",
            ):
                pass

        mock_llm_cls.assert_called_once_with(
            model="claude-opus-4-20250514",
            temperature=1.0,
            max_tokens=4000,
        )

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_streaming_context_matches_non_streaming(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
        story_history,
    ):
        """The context built for streaming should contain the same key info as non-streaming."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        captured_context = {}

        async def mock_astream(input_dict):
            captured_context.update(input_dict)
            yield MagicMock(content="token")

        mock_chain = MagicMock()
        mock_chain.astream = mock_astream

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            async for _ in generate_narrative_streaming(
                judgments=sample_judgments,
                characters=sample_characters,
                world_context=world_context,
                story_history=story_history,
            ):
                pass

        context = captured_context["context"]

        # Should contain the same core elements as non-streaming
        assert "Ella" in context
        assert "Kael" in context
        assert "Swing sword at the goblin" in context
        assert "Sneak behind the enemy" in context
        assert "dark medieval fantasy world" in context
        assert "The party entered the dark cave." in context
        assert "대성공" in context
        assert "성공" in context

    @pytest.mark.asyncio
    @patch("app.services.ai_nodes.narrative_node.ChatLiteLLM")
    @patch("app.services.ai_nodes.narrative_node.load_prompt")
    async def test_streaming_partial_yield_before_error(
        self,
        mock_load_prompt,
        mock_llm_cls,
        sample_judgments,
        sample_characters,
        world_context,
        story_history,
    ):
        """Tokens yielded before an error should still be collected by the caller."""
        mock_load_prompt.return_value = MagicMock(content="System prompt")

        async def mock_astream_partial(input_dict):
            yield MagicMock(content="first")
            yield MagicMock(content="second")
            raise RuntimeError("Connection lost mid-stream")

        mock_chain = MagicMock()
        mock_chain.astream = mock_astream_partial

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch(
            "app.services.ai_nodes.narrative_node.ChatPromptTemplate"
        ) as mock_template_cls:
            mock_template = MagicMock()
            mock_template.__or__ = MagicMock(return_value=mock_chain)
            mock_template_cls.from_messages.return_value = mock_template

            tokens = []
            with pytest.raises(ValueError, match="서술 스트리밍 실패"):
                async for token in generate_narrative_streaming(
                    judgments=sample_judgments,
                    characters=sample_characters,
                    world_context=world_context,
                    story_history=story_history,
                ):
                    tokens.append(token)

        # The two tokens yielded before the error should have been collected
        assert tokens == ["first", "second"]
