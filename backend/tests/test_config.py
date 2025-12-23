"""
Tests for configuration validation module.

Requirements:
- 4.2: LiteLLM이 구성될 때 시스템은 OpenAI GPT-4o를 주요 모델로 지원해야 합니다
- 8.1: AI GM이 초기화될 때 시스템은 구성 가능한 마크다운 파일 경로에서 시스템 프롬프트를 로드해야 합니다
- 8.2: 마크다운 파일이 누락될 때 시스템은 파일 경로를 나타내는 명확한 오류를 발생시켜야 합니다
- 11.3: 시스템 프롬프트 파일을 읽을 수 없을 때 시스템은 시작 시 구성 오류를 발생시켜야 합니다
"""

import pytest

from app.config import AIGMConfig, ConfigurationError


class TestAIGMConfig:
    """Test AI GM configuration validation."""

    # ===== OpenAI API Key Tests =====

    def test_validate_with_missing_openai_api_key_for_gpt_model(self, monkeypatch):
        """Test that validation fails when OPENAI_API_KEY is missing for GPT model."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("SYSTEM_PROMPT_PATH", "app/prompts/system_prompt.md")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")

        config = AIGMConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        assert "OPENAI_API_KEY" in str(exc_info.value)

    def test_validate_with_placeholder_openai_api_key(self, monkeypatch):
        """Test that validation fails when OPENAI_API_KEY is placeholder."""
        monkeypatch.setenv("OPENAI_API_KEY", "your_openai_api_key_here")
        monkeypatch.setenv("SYSTEM_PROMPT_PATH", "app/prompts/system_prompt.md")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")

        config = AIGMConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        assert "placeholder" in str(exc_info.value).lower()

    def test_validate_with_valid_openai_config(self, monkeypatch):
        """Test that validation succeeds with valid OpenAI configuration."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai-key-123")
        monkeypatch.setenv("SYSTEM_PROMPT_PATH", "app/prompts/system_prompt.md")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")

        config = AIGMConfig()
        config.validate()

        assert config.openai_api_key == "sk-test-openai-key-123"
        assert config.llm_model == "gpt-4o"
        assert config.get_api_key() == "sk-test-openai-key-123"

    # ===== Gemini API Key Tests =====

    def test_validate_with_missing_gemini_api_key(self, monkeypatch):
        """Test that validation fails when GEMINI_API_KEY is missing for Gemini model."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("SYSTEM_PROMPT_PATH", "app/prompts/system_prompt.md")
        monkeypatch.setenv("LLM_MODEL", "gemini/gemini-3-pro-preview")

        config = AIGMConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        assert "GEMINI_API_KEY" in str(exc_info.value)

    def test_validate_with_placeholder_gemini_api_key(self, monkeypatch):
        """Test that validation fails when GEMINI_API_KEY is placeholder."""
        monkeypatch.setenv("GEMINI_API_KEY", "your_google_api_key_here")
        monkeypatch.setenv("SYSTEM_PROMPT_PATH", "app/prompts/system_prompt.md")
        monkeypatch.setenv("LLM_MODEL", "gemini/gemini-3-pro-preview")

        config = AIGMConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        assert "placeholder" in str(exc_info.value).lower()

    def test_validate_with_valid_gemini_config(self, monkeypatch):
        """Test that validation succeeds with valid Gemini configuration."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key-123")
        monkeypatch.setenv("SYSTEM_PROMPT_PATH", "app/prompts/system_prompt.md")
        monkeypatch.setenv("LLM_MODEL", "gemini/gemini-3-pro-preview")

        config = AIGMConfig()
        config.validate()

        assert config.gemini_api_key == "test-gemini-key-123"
        assert config.llm_model == "gemini/gemini-3-pro-preview"
        assert config.get_api_key() == "test-gemini-key-123"

    # ===== System Prompt Tests (Requirements 8.1, 8.2, 11.3) =====

    def test_validate_with_missing_system_prompt(self, monkeypatch):
        """Test that validation fails when system prompt file doesn't exist (Req 8.2)."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai-key-123")
        monkeypatch.setenv("SYSTEM_PROMPT_PATH", "nonexistent/path/prompt.md")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")

        config = AIGMConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        error_msg = str(exc_info.value)
        assert "System prompt file not found" in error_msg
        assert "nonexistent/path/prompt.md" in error_msg

    def test_validate_with_empty_system_prompt(self, monkeypatch, tmp_path):
        """Test that validation fails when system prompt file is empty (Req 11.3)."""
        # Create an empty file
        empty_prompt = tmp_path / "empty_prompt.md"
        empty_prompt.write_text("")

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai-key-123")
        monkeypatch.setenv("SYSTEM_PROMPT_PATH", str(empty_prompt))
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")

        config = AIGMConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        assert "empty" in str(exc_info.value).lower()

    def test_validate_with_valid_system_prompt(self, monkeypatch, tmp_path):
        """Test that validation succeeds with valid system prompt file (Req 8.1)."""
        # Create a valid prompt file
        valid_prompt = tmp_path / "valid_prompt.md"
        valid_prompt.write_text("# TRPG System Prompt\n\nThis is a valid prompt.")

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai-key-123")
        monkeypatch.setenv("SYSTEM_PROMPT_PATH", str(valid_prompt))
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")

        config = AIGMConfig()
        config.validate()

        assert config.system_prompt_path == str(valid_prompt)

    # ===== Default LLM Model Tests (Requirement 4.2) =====

    def test_validate_with_default_llm_model(self, monkeypatch):
        """Test that LLM_MODEL defaults to gpt-4o if not set (Req 4.2)."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai-key-123")
        monkeypatch.setenv("SYSTEM_PROMPT_PATH", "app/prompts/system_prompt.md")
        monkeypatch.delenv("LLM_MODEL", raising=False)

        config = AIGMConfig()
        config.validate()

        assert config.llm_model == "gpt-4o"

    # ===== Model Type Detection Tests =====

    def test_is_openai_model_detection(self):
        """Test OpenAI model detection."""
        config = AIGMConfig()

        # OpenAI models
        assert config._is_openai_model("gpt-4o") is True
        assert config._is_openai_model("gpt-4-turbo") is True
        assert config._is_openai_model("gpt-3.5-turbo") is True
        assert config._is_openai_model("o1-preview") is True

        # Non-OpenAI models
        assert config._is_openai_model("gemini/gemini-pro") is False
        assert config._is_openai_model("google/gemini-pro") is False

    def test_is_gemini_model_detection(self):
        """Test Gemini model detection."""
        config = AIGMConfig()

        # Gemini models
        assert config._is_gemini_model("gemini/gemini-pro") is True
        assert config._is_gemini_model("gemini/gemini-3-pro-preview") is True
        assert config._is_gemini_model("google/gemini-pro") is True

        # Non-Gemini models
        assert config._is_gemini_model("gpt-4o") is False
        assert config._is_gemini_model("gpt-4-turbo") is False

    # ===== Helper Method Tests =====

    def test_get_api_key_before_validation(self):
        """Test that get_api_key raises error before validation."""
        config = AIGMConfig()

        with pytest.raises(ConfigurationError) as exc_info:
            config.get_api_key()

        assert "not been validated" in str(exc_info.value)

    def test_get_system_prompt_full_path(self, monkeypatch):
        """Test getting full path to system prompt file."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai-key-123")
        monkeypatch.setenv("SYSTEM_PROMPT_PATH", "app/prompts/system_prompt.md")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")

        config = AIGMConfig()
        config.validate()

        full_path = config.get_system_prompt_full_path()
        assert full_path.exists()
        assert full_path.name == "system_prompt.md"

    def test_is_validated_property(self, monkeypatch):
        """Test is_validated property."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai-key-123")
        monkeypatch.setenv("SYSTEM_PROMPT_PATH", "app/prompts/system_prompt.md")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")

        config = AIGMConfig()
        assert config.is_validated is False

        config.validate()
        assert config.is_validated is True
