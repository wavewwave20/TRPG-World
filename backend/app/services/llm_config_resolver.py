"""LLM configuration resolver.

Checks DB for active LLM model + provider API key, falls back to env vars.
"""

import logging
import os

from app.database import SessionLocal
from app.models import LLMApiKey, LLMModel
from app.utils.encryption import decrypt_api_key

logger = logging.getLogger("ai_gm.llm_config")


class LLMConfig:
    """Resolved LLM configuration."""

    def __init__(self, model_id: str, source: str):
        self.model_id = model_id
        self.source = source  # "database" or "environment"


def _set_env_key_for_provider(provider: str, api_key: str):
    """Set the appropriate environment variable for LiteLLM based on provider."""
    if provider == "gemini":
        os.environ["GEMINI_API_KEY"] = api_key
    elif provider == "anthropic":
        os.environ["ANTHROPIC_API_KEY"] = api_key
    else:
        os.environ["OPENAI_API_KEY"] = api_key


def resolve_llm_config() -> LLMConfig:
    """Resolve the active LLM configuration.

    Priority:
    1. Database: if an is_active=True LLMModel exists with a matching API key
    2. Environment: fall back to LLM_MODEL env var
    """
    db = SessionLocal()
    try:
        active_model = (
            db.query(LLMModel)
            .filter(LLMModel.is_active == True)  # noqa: E712
            .first()
        )

        if active_model:
            api_key_row = (
                db.query(LLMApiKey)
                .filter(LLMApiKey.provider == active_model.provider)
                .first()
            )

            if api_key_row:
                try:
                    plain_key = decrypt_api_key(api_key_row.api_key_encrypted)
                    _set_env_key_for_provider(active_model.provider, plain_key)
                except Exception as e:
                    logger.error(f"Failed to decrypt API key for provider {active_model.provider}: {e}")
                    return LLMConfig(
                        model_id=os.getenv("LLM_MODEL", "gpt-4o"),
                        source="environment",
                    )

                logger.debug(
                    f"Using DB LLM config: {active_model.display_name} "
                    f"({active_model.model_id})"
                )
                return LLMConfig(
                    model_id=active_model.model_id,
                    source="database",
                )
            else:
                logger.warning(f"Active model '{active_model.model_id}' has no API key for provider '{active_model.provider}'")

    except Exception as e:
        logger.warning(f"Failed to query LLM settings from DB: {e}")
    finally:
        db.close()

    return LLMConfig(
        model_id=os.getenv("LLM_MODEL", "gpt-4o"),
        source="environment",
    )


def get_active_llm_model() -> str:
    """Convenience function: returns just the model_id string."""
    return resolve_llm_config().model_id
