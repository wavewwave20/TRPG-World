"""LLM 설정 관리 라우트 (관리자 전용).

프로바이더별 API 키 관리 + 모델 등록/선택을 분리합니다.
"""

import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LLMApiKey, LLMModel
from app.routes.auth import verify_admin
from app.utils.encryption import decrypt_api_key, encrypt_api_key

router = APIRouter(prefix="/api/llm-settings", tags=["llm-settings"])


# --- Pydantic Schemas ---


class ApiKeySetRequest(BaseModel):
    api_key: str


class ApiKeyResponse(BaseModel):
    provider: str
    provider_display: str
    api_key_masked: str
    updated_at: str


class ModelCreateRequest(BaseModel):
    provider: str
    model_id: str
    display_name: str


class ModelResponse(BaseModel):
    id: int
    provider: str
    model_id: str
    display_name: str
    is_active: bool
    is_active_story: bool
    is_active_judgment: bool
    has_api_key: bool
    created_at: str


class LLMSettingsResponse(BaseModel):
    api_keys: list[ApiKeyResponse]
    models: list[ModelResponse]
    active_model: ModelResponse | None
    active_story_model: ModelResponse | None
    active_judgment_model: ModelResponse | None
    active_source: str
    active_story_source: str
    active_judgment_source: str
    env_model: str | None
    env_story_model: str | None
    env_judgment_model: str | None


VALID_PURPOSES = {"story", "judgment"}


# --- Helpers ---


def _mask_api_key(encrypted_key: str) -> str:
    """Decrypt and mask an API key for display."""
    try:
        plain = decrypt_api_key(encrypted_key)
        if len(plain) <= 8:
            return "****"
        return plain[:3] + "..." + plain[-4:]
    except Exception:
        return "****"


def _apply_model_to_env(model: LLMModel, db: Session):
    """Set the API key env var for the active model's provider."""
    api_key_row = db.query(LLMApiKey).filter(LLMApiKey.provider == model.provider).first()
    if not api_key_row:
        return

    plain_key = decrypt_api_key(api_key_row.api_key_encrypted)

    if model.provider == "gemini":
        os.environ["GEMINI_API_KEY"] = plain_key
    elif model.provider == "anthropic":
        os.environ["ANTHROPIC_API_KEY"] = plain_key
    else:
        os.environ["OPENAI_API_KEY"] = plain_key


def _normalize_purpose(purpose: str) -> str:
    normalized = (purpose or "story").strip().lower()
    if normalized not in VALID_PURPOSES:
        raise HTTPException(status_code=400, detail=f"Invalid purpose: {purpose}")
    return normalized


def _is_any_active(model: LLMModel) -> bool:
    return bool(model.is_active_story or model.is_active_judgment)


PROVIDERS = [
    {"provider": "openai", "display": "OpenAI"},
    {"provider": "gemini", "display": "Google Gemini"},
    {"provider": "anthropic", "display": "Anthropic"},
]


# --- Endpoints: Overview ---


@router.get("/", response_model=LLMSettingsResponse)
def get_llm_settings(user_id: int, db: Session = Depends(get_db)):
    """Get all LLM settings (API keys + models). Admin only."""
    verify_admin(user_id, db)

    # API keys
    api_key_rows = db.query(LLMApiKey).all()
    api_key_map = {row.provider: row for row in api_key_rows}

    api_keys_resp = []
    for p in PROVIDERS:
        row = api_key_map.get(p["provider"])
        if row:
            api_keys_resp.append(
                ApiKeyResponse(
                    provider=row.provider,
                    provider_display=row.provider_display,
                    api_key_masked=_mask_api_key(row.api_key_encrypted),
                    updated_at=row.updated_at.isoformat(),
                )
            )
        else:
            api_keys_resp.append(
                ApiKeyResponse(
                    provider=p["provider"],
                    provider_display=p["display"],
                    api_key_masked="",
                    updated_at="",
                )
            )

    # Models
    models = db.query(LLMModel).order_by(LLMModel.created_at.desc()).all()
    models_resp = []
    active_model = None
    active_story_model = None
    active_judgment_model = None
    for m in models:
        resp = ModelResponse(
            id=m.id,
            provider=m.provider,
            model_id=m.model_id,
            display_name=m.display_name,
            is_active=_is_any_active(m),
            is_active_story=bool(m.is_active_story),
            is_active_judgment=bool(m.is_active_judgment),
            has_api_key=m.provider in api_key_map,
            created_at=m.created_at.isoformat(),
        )
        models_resp.append(resp)
        if resp.is_active_story:
            active_story_model = resp
        if resp.is_active_judgment:
            active_judgment_model = resp

    active_model = active_story_model or active_judgment_model

    active_story_in_db = active_story_model is not None
    active_judgment_in_db = active_judgment_model is not None

    return LLMSettingsResponse(
        api_keys=api_keys_resp,
        models=models_resp,
        active_model=active_model,
        active_story_model=active_story_model,
        active_judgment_model=active_judgment_model,
        active_source="database" if active_story_in_db else "environment",
        active_story_source="database" if active_story_in_db else "environment",
        active_judgment_source="database" if active_judgment_in_db else "environment",
        env_model=os.getenv("LLM_MODEL", "gpt-4o"),
        env_story_model=os.getenv("LLM_MODEL_STORY") or os.getenv("LLM_MODEL") or "gpt-4o",
        env_judgment_model=os.getenv("LLM_MODEL_JUDGMENT")
        or os.getenv("LLM_MODEL_FAST")
        or os.getenv("LLM_MODEL")
        or "gpt-4o-mini",
    )


# --- Endpoints: API Keys ---


@router.put("/api-keys/{provider}", response_model=ApiKeyResponse)
def set_api_key(provider: str, body: ApiKeySetRequest, user_id: int, db: Session = Depends(get_db)):
    """Set or update an API key for a provider. Admin only."""
    verify_admin(user_id, db)

    provider_info = next((p for p in PROVIDERS if p["provider"] == provider), None)
    if not provider_info:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    now = datetime.utcnow()
    row = db.query(LLMApiKey).filter(LLMApiKey.provider == provider).first()

    if row:
        row.api_key_encrypted = encrypt_api_key(body.api_key)
        row.updated_at = now
    else:
        row = LLMApiKey(
            provider=provider,
            provider_display=provider_info["display"],
            api_key_encrypted=encrypt_api_key(body.api_key),
            created_at=now,
            updated_at=now,
        )
        db.add(row)

    db.commit()
    db.refresh(row)

    # If active model uses this provider, update env
    active = (
        db.query(LLMModel)
        .filter(
            LLMModel.provider == provider,
            ((LLMModel.is_active_story == True) | (LLMModel.is_active_judgment == True)),  # noqa: E712
        )
        .first()
    )
    if active:
        _apply_model_to_env(active, db)

    return ApiKeyResponse(
        provider=row.provider,
        provider_display=row.provider_display,
        api_key_masked=_mask_api_key(row.api_key_encrypted),
        updated_at=row.updated_at.isoformat(),
    )


@router.delete("/api-keys/{provider}")
def delete_api_key(provider: str, user_id: int, db: Session = Depends(get_db)):
    """Delete an API key for a provider. Admin only."""
    verify_admin(user_id, db)

    row = db.query(LLMApiKey).filter(LLMApiKey.provider == provider).first()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")

    # Check if any active model uses this provider
    active = (
        db.query(LLMModel)
        .filter(
            LLMModel.provider == provider,
            ((LLMModel.is_active_story == True) | (LLMModel.is_active_judgment == True)),  # noqa: E712
        )
        .first()
    )
    if active:
        raise HTTPException(status_code=400, detail="Cannot delete API key while an active model uses this provider")

    db.delete(row)
    db.commit()

    return {"message": f"API key for {provider} deleted"}


# --- Endpoints: Models ---


@router.post("/models", response_model=ModelResponse, status_code=201)
def add_model(body: ModelCreateRequest, user_id: int, db: Session = Depends(get_db)):
    """Register a new model. Admin only."""
    verify_admin(user_id, db)

    provider_info = next((p for p in PROVIDERS if p["provider"] == body.provider), None)
    if not provider_info:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {body.provider}")

    existing = db.query(LLMModel).filter(LLMModel.model_id == body.model_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Model '{body.model_id}' already registered")

    has_key = db.query(LLMApiKey).filter(LLMApiKey.provider == body.provider).first() is not None

    model = LLMModel(
        provider=body.provider,
        model_id=body.model_id,
        display_name=body.display_name,
        is_active=False,
        created_at=datetime.utcnow(),
    )
    db.add(model)
    db.commit()
    db.refresh(model)

    return ModelResponse(
        id=model.id,
        provider=model.provider,
        model_id=model.model_id,
        display_name=model.display_name,
        is_active=_is_any_active(model),
        is_active_story=bool(model.is_active_story),
        is_active_judgment=bool(model.is_active_judgment),
        has_api_key=has_key,
        created_at=model.created_at.isoformat(),
    )


@router.delete("/models/{model_id}")
def remove_model(model_id: int, user_id: int, db: Session = Depends(get_db)):
    """Remove a registered model. Admin only."""
    verify_admin(user_id, db)

    model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    if _is_any_active(model):
        raise HTTPException(status_code=400, detail="Cannot delete active model. Deactivate first.")

    db.delete(model)
    db.commit()

    return {"message": f"Model '{model.model_id}' removed"}


@router.post("/models/{model_id}/activate", response_model=ModelResponse)
def activate_model(
    model_id: int,
    user_id: int,
    purpose: str = Query("story"),
    db: Session = Depends(get_db),
):
    verify_admin(user_id, db)
    normalized_purpose = _normalize_purpose(purpose)

    model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    # Check API key exists
    has_key = db.query(LLMApiKey).filter(LLMApiKey.provider == model.provider).first()
    if not has_key:
        raise HTTPException(
            status_code=400, detail=f"No API key set for provider '{model.provider}'. Set an API key first."
        )

    if normalized_purpose == "judgment":
        db.query(LLMModel).update({"is_active_judgment": False})
        model.is_active_judgment = True
    else:
        db.query(LLMModel).update({"is_active_story": False})
        model.is_active_story = True

    model.is_active = _is_any_active(model)

    for other in db.query(LLMModel).filter(LLMModel.id != model_id).all():
        other.is_active = _is_any_active(other)

    db.commit()
    db.refresh(model)

    _apply_model_to_env(model, db)

    return ModelResponse(
        id=model.id,
        provider=model.provider,
        model_id=model.model_id,
        display_name=model.display_name,
        is_active=_is_any_active(model),
        is_active_story=bool(model.is_active_story),
        is_active_judgment=bool(model.is_active_judgment),
        has_api_key=True,
        created_at=model.created_at.isoformat(),
    )


@router.post("/models/{model_id}/deactivate", response_model=ModelResponse)
def deactivate_model(
    model_id: int,
    user_id: int,
    purpose: str = Query("story"),
    db: Session = Depends(get_db),
):
    verify_admin(user_id, db)
    normalized_purpose = _normalize_purpose(purpose)

    model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    if normalized_purpose == "judgment":
        model.is_active_judgment = False
    else:
        model.is_active_story = False
    model.is_active = _is_any_active(model)

    for other in db.query(LLMModel).filter(LLMModel.id != model.id).all():
        other.is_active = _is_any_active(other)

    db.commit()
    db.refresh(model)

    has_key = db.query(LLMApiKey).filter(LLMApiKey.provider == model.provider).first() is not None

    return ModelResponse(
        id=model.id,
        provider=model.provider,
        model_id=model.model_id,
        display_name=model.display_name,
        is_active=_is_any_active(model),
        is_active_story=bool(model.is_active_story),
        is_active_judgment=bool(model.is_active_judgment),
        has_api_key=has_key,
        created_at=model.created_at.isoformat(),
    )


@router.post("/models/{model_id}/test")
def test_model_connection(model_id: int, user_id: int, db: Session = Depends(get_db)):
    """Test a model connection. Admin only."""
    verify_admin(user_id, db)

    model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    api_key_row = db.query(LLMApiKey).filter(LLMApiKey.provider == model.provider).first()
    if not api_key_row:
        return {"success": False, "message": f"No API key set for provider '{model.provider}'"}

    try:
        import litellm

        plain_key = decrypt_api_key(api_key_row.api_key_encrypted)

        response = litellm.completion(
            model=model.model_id,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5,
            api_key=plain_key,
        )
        return {
            "success": True,
            "message": f"Connection successful. Model: {response.model}",
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection failed: {e!s}",
        }
