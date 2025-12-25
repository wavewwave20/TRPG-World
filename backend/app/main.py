import logging
import sys

import litellm
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from litellm.integrations.custom_logger import CustomLogger

from app.config import ConfigurationError, validate_ai_gm_config
from app.routes import auth, characters, sessions, story_logs
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
        llm_logger.info(f"[LlmUsage] 모델: {model}, 토큰 사용량: {usage}, 비용: {cost}, 소요 시간: {end_time - start_time}초")

litellm.callbacks = [LLMUsageLogger()]

# Ensure stdout uses UTF-8 encoding
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

logger = logging.getLogger(__name__)

# Validate AI GM configuration at startup
try:
    validate_ai_gm_config()
except ConfigurationError as e:
    logger.error(f"Configuration validation failed: {e}")
    logger.warning("AI GM features will not be available until configuration is fixed")
    # Note: We don't raise here to allow the app to start for non-AI features
    # In production, you might want to raise to prevent startup with invalid config

app = FastAPI(title="TRPG World API", version="0.1.0")

# CORS configuration for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite default port
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

# Create Socket.io ASGI app and mount it to FastAPI
socket_app = socketio.ASGIApp(sio, app)

# Export socket_app as the main application
# This should be used in uvicorn: uvicorn app.main:socket_app
app = socket_app
