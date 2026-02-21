import logging
import os
import sys
from pathlib import Path

import litellm
import socketio
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from litellm.integrations.custom_logger import CustomLogger

from app.config import ConfigurationError, validate_ai_gm_config
from app.routes import auth, characters, llm_settings, sessions, story_logs
from app.socket_server import sio

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Reduce Socket.io and engineio logging noise (heartbeat 등 불필요한 로그 제거)
logging.getLogger("socketio.server").setLevel(logging.ERROR)
logging.getLogger("engineio.server").setLevel(logging.ERROR)

# Disable LiteLLM's internal verbose logging (prevents duplicate log messages)


litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.WARNING)

# Custom LiteLLM logger for usage tracking
llm_logger = logging.getLogger("ai_gm.llm_usage")


class LLMUsageLogger(CustomLogger):
    def log_pre_api_call(self, model, messages, kwargs):
        """LLM API 호출 시작 시점에 로그"""
        llm_logger.info(f"[LlmCall] 모델: {model} 호출 시작")

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        model = kwargs.get("model")
        usage = response_obj.get("usage", {})
        cost = kwargs.get("response_cost", 0)
        llm_logger.info(
            f"[LlmUsage] 모델: {model}, 토큰 사용량: {usage}, 비용: {cost}, 소요 시간: {end_time - start_time}초"
        )


litellm.callbacks = [LLMUsageLogger()]

# Ensure stdout uses UTF-8 encoding
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

logger = logging.getLogger(__name__)


def _normalize_langsmith_env() -> None:
    """LangSmith/LangChain tracing 환경변수를 호환되게 정규화합니다."""
    tracing = os.getenv("LANGSMITH_TRACING", "false").strip().lower()
    tracing_enabled = tracing in {"1", "true", "yes", "on"}

    # 최신/레거시 키 모두 세팅해서 누락 방지
    os.environ["LANGSMITH_TRACING"] = "true" if tracing_enabled else "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "true" if tracing_enabled else "false"

    if os.getenv("LANGSMITH_API_KEY") and not os.getenv("LANGCHAIN_API_KEY"):
        os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY", "")

    if os.getenv("LANGSMITH_ENDPOINT") and not os.getenv("LANGCHAIN_ENDPOINT"):
        os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGSMITH_ENDPOINT", "")

    if os.getenv("LANGSMITH_PROJECT") and not os.getenv("LANGCHAIN_PROJECT"):
        os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT", "")

    # LiteLLM direct-call 경로도 LangSmith로 보낼 수 있게 설정
    # (LangChain 경로는 위 env만으로 추적됨)
    if tracing_enabled:
        try:
            existing_success = list(getattr(litellm, "success_callback", []) or [])
            if "langsmith" not in existing_success:
                existing_success.append("langsmith")
                litellm.success_callback = existing_success

            existing_failure = list(getattr(litellm, "failure_callback", []) or [])
            if "langsmith" not in existing_failure:
                existing_failure.append("langsmith")
                litellm.failure_callback = existing_failure
        except Exception as e:
            logger.warning(f"LiteLLM LangSmith callback 설정 실패: {e}")

    logger.info(
        "LangSmith tracing normalized: "
        f"enabled={tracing_enabled}, project={os.getenv('LANGSMITH_PROJECT','') or os.getenv('LANGCHAIN_PROJECT','')}"
    )


def run_startup_migrations() -> None:
    """Apply pending Alembic migrations before serving requests."""
    project_root = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")


# Tracing env normalization (LangSmith/LangChain/LiteLLM)
_normalize_langsmith_env()

# Validate AI GM configuration at startup
try:
    validate_ai_gm_config()
except ConfigurationError as e:
    logger.error(f"Configuration validation failed: {e}")
    logger.warning("AI GM features will not be available until configuration is fixed")
    # Note: We don't raise here to allow the app to start for non-AI features
    # In production, you might want to raise to prevent startup with invalid config

app = FastAPI(title="TRPG World API", version="0.1.0")


@app.on_event("startup")
async def on_startup():
    """Ensure database schema is at latest version and apply active LLM config."""
    run_startup_migrations()

    # Apply active LLM setting from DB (if any)
    try:
        from app.services.llm_config_resolver import resolve_llm_config

        config = resolve_llm_config()
        logger.info(f"LLM config resolved: model={config.model_id}, source={config.source}")
    except Exception as e:
        logger.warning(f"Failed to resolve LLM config from DB: {e}")

# CORS configuration - configurable via environment variable
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint to verify service status."""
    return {"status": "ok", "service": "trpg-world"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "TRPG World API", "version": "0.1.0"}


# Register API routers
app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(characters.router)
app.include_router(story_logs.router)
app.include_router(llm_settings.router)

# Create Socket.io ASGI app and mount it to FastAPI
socket_app = socketio.ASGIApp(sio, app)

# Export socket_app as the main application
# This should be used in uvicorn: uvicorn app.main:socket_app
app = socket_app
