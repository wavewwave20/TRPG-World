"""
Configuration validation module for AI Game Master system.

This module validates required environment variables and system files
at application startup to ensure the AI GM system can function properly.

Requirements:
- 4.2: LiteLLM이 구성될 때 시스템은 OpenAI GPT-4o를 주요 모델로 지원해야 합니다
- 8.1: AI GM이 초기화될 때 시스템은 구성 가능한 마크다운 파일 경로에서 시스템 프롬프트를 로드해야 합니다
- 8.2: 마크다운 파일이 누락될 때 시스템은 파일 경로를 나타내는 명확한 오류를 발생시켜야 합니다
- 11.3: 시스템 프롬프트 파일을 읽을 수 없을 때 시스템은 시작 시 구성 오류를 발생시켜야 합니다
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """필수 설정이 누락되거나 잘못되었을 때 발생."""

    pass


class AIGMConfig:
    """AI Game Master configuration validator and holder."""

    # Default values
    DEFAULT_LLM_MODEL = "gpt-4o"
    DEFAULT_SYSTEM_PROMPT_PATH = "app/prompts/system_prompt.md"

    def __init__(self):
        """Initialize configuration with default values."""
        self.openai_api_key: str | None = None
        self.gemini_api_key: str | None = None
        self.system_prompt_path: str = self.DEFAULT_SYSTEM_PROMPT_PATH
        self.llm_model: str = self.DEFAULT_LLM_MODEL
        self._validated: bool = False

    def _is_openai_model(self, model: str) -> bool:
        """Check if the model is an OpenAI model."""
        openai_prefixes = ("gpt-", "o1-", "o3-", "text-", "davinci", "curie", "babbage", "ada")
        return model.startswith(openai_prefixes) or "/" not in model

    def _is_gemini_model(self, model: str) -> bool:
        """Check if the model is a Gemini model."""
        return model.startswith("gemini/") or model.startswith("google/")

    def validate(self) -> None:
        """
        Validate all required configuration at startup.

        Validates:
        - API key exists for the configured model (OPENAI_API_KEY or GEMINI_API_KEY)
        - SYSTEM_PROMPT_PATH points to an existing, readable, non-empty file
        - LLM_MODEL is set (uses gpt-4o as default per requirement 4.2)

        Raises:
            ConfigurationError: If any required configuration is missing or invalid
        """
        errors = []
        warnings = []

        # Load LLM_MODEL first to determine which API key is needed
        self.llm_model = os.getenv("LLM_MODEL", self.DEFAULT_LLM_MODEL)
        if not self.llm_model:
            warnings.append(f"LLM_MODEL is empty, using default: {self.DEFAULT_LLM_MODEL}")
            self.llm_model = self.DEFAULT_LLM_MODEL

        # Load API keys
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")

        # Validate API key based on model type
        if self._is_gemini_model(self.llm_model):
            # Gemini model requires GEMINI_API_KEY
            if not self.gemini_api_key:
                errors.append(
                    f"GEMINI_API_KEY environment variable is not set.\n"
                    f"  This is required for Gemini model: {self.llm_model}"
                )
            elif self.gemini_api_key == "your_google_api_key_here":
                errors.append("GEMINI_API_KEY is set to placeholder value.\n  Please provide a valid Google API key")
        # OpenAI or other model requires OPENAI_API_KEY
        elif not self.openai_api_key:
            errors.append(
                f"OPENAI_API_KEY environment variable is not set.\n  This is required for model: {self.llm_model}"
            )
        elif self.openai_api_key == "your_openai_api_key_here":
            errors.append("OPENAI_API_KEY is set to placeholder value.\n  Please provide a valid OpenAI API key")

        # Validate SYSTEM_PROMPT_PATH (requirement 8.1, 8.2, 11.3)
        self.system_prompt_path = os.getenv("SYSTEM_PROMPT_PATH", self.DEFAULT_SYSTEM_PROMPT_PATH)

        # Convert to absolute path if relative
        if not os.path.isabs(self.system_prompt_path):
            # Assume path is relative to backend directory
            backend_dir = Path(__file__).parent.parent
            prompt_path = backend_dir / self.system_prompt_path
        else:
            prompt_path = Path(self.system_prompt_path)

        # Requirement 8.2: Clear error when file is missing
        if not prompt_path.exists():
            errors.append(
                f"System prompt file not found at: {prompt_path}\n"
                f"  SYSTEM_PROMPT_PATH={self.system_prompt_path}\n"
                f"  Please create the system prompt markdown file at the specified path"
            )
        elif not prompt_path.is_file():
            errors.append(f"System prompt path exists but is not a file: {prompt_path}")
        else:
            # Requirement 11.3: Verify file is readable and not empty
            try:
                content = prompt_path.read_text(encoding="utf-8")
                if not content.strip():
                    errors.append(
                        f"System prompt file is empty: {prompt_path}\n"
                        f"  The system prompt file must contain TRPG rules and guidelines"
                    )
            except UnicodeDecodeError as e:
                errors.append(
                    f"System prompt file has invalid encoding at {prompt_path}\n"
                    f"  Please ensure the file is UTF-8 encoded: {e}"
                )
            except PermissionError as e:
                errors.append(f"Cannot read system prompt file (permission denied) at {prompt_path}: {e}")
            except Exception as e:
                errors.append(f"Cannot read system prompt file at {prompt_path}: {e}")

        # Log warnings
        for warning in warnings:
            logger.warning(warning)

        # If there are any errors, raise ConfigurationError
        if errors:
            error_message = "AI GM Configuration validation failed:\n" + "\n".join(f"  - {err}" for err in errors)
            raise ConfigurationError(error_message)

        self._validated = True
        logger.info("AI GM configuration validated successfully")
        logger.info(f"  LLM Model: {self.llm_model}")
        logger.info(f"  System Prompt: {self.system_prompt_path}")

    @property
    def is_validated(self) -> bool:
        """Check if configuration has been validated."""
        return self._validated

    def get_api_key(self) -> str:
        """
        Get the appropriate API key for the configured model.

        Returns:
            str: The API key for the configured LLM model

        Raises:
            ConfigurationError: If configuration has not been validated
        """
        if not self._validated:
            raise ConfigurationError("Configuration has not been validated. Call validate() first.")

        if self._is_gemini_model(self.llm_model):
            return self.gemini_api_key
        return self.openai_api_key

    def get_system_prompt_full_path(self) -> Path:
        """
        Get the full absolute path to the system prompt file.

        Returns:
            Path: Absolute path to the system prompt file
        """
        if not os.path.isabs(self.system_prompt_path):
            backend_dir = Path(__file__).parent.parent
            return backend_dir / self.system_prompt_path
        return Path(self.system_prompt_path)


# Global configuration instance
ai_gm_config = AIGMConfig()


def validate_ai_gm_config() -> None:
    """
    Validate AI GM configuration at application startup.

    This function should be called during application initialization
    to ensure all required configuration is present and valid.

    Requirements:
    - 8.2: Raises clear error when system prompt file is missing
    - 11.3: Raises configuration error when system prompt file cannot be read

    Raises:
        ConfigurationError: If configuration validation fails
    """
    ai_gm_config.validate()


def get_config() -> AIGMConfig:
    """
    Get the validated AI GM configuration.

    Returns:
        AIGMConfig: The validated configuration instance

    Raises:
        ConfigurationError: If configuration has not been validated
    """
    if not ai_gm_config.is_validated:
        raise ConfigurationError(
            "AI GM configuration has not been validated. Call validate_ai_gm_config() during application startup."
        )
    return ai_gm_config
