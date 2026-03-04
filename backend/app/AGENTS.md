# BACKEND APP KNOWLEDGE BASE

## OVERVIEW
`backend/app` is runtime backend code: API routes, AI services, socket runtime, config, DB access, and shared utils.

## STRUCTURE
```text
backend/app/
|- main.py                 # FastAPI + startup migration + Socket.IO mount
|- routes/                 # HTTP API boundaries
|- services/               # AI orchestration and game logic
|- socket/                 # realtime server internals
|- prompts/                # LLM prompt templates
|- database.py             # SQLAlchemy engine/session wiring
|- models.py / schemas.py  # ORM + DTO contracts
`- utils/                  # shared backend helpers
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Startup behavior | `backend/app/main.py` | Runs migrations, normalizes tracing env, mounts ASGI socket app |
| Auth/session APIs | `backend/app/routes/*.py` | All REST endpoints are defined per domain router |
| LLM config resolution | `backend/app/services/llm_config_resolver.py` | Active model settings source of truth |
| AI gameplay orchestration | `backend/app/services/ai_gm_service_v2.py` | Main staged flow coordination |
| Story arc control | `backend/app/services/story_director.py` | Narrative continuity and drift guardrails |
| Prompt loading | `backend/app/utils/prompt_loader.py` | Runtime prompt file access |

## CONVENTIONS
- Keep route handlers thin; place gameplay/business logic in `services/`.
- Preserve staged gameplay model (analysis/judgment -> dice -> narrative) in service-level code.
- `app.socket_server` is compatibility surface; new socket internals belong in `app/socket/*`.
- SQLAlchemy models stay in `models.py`; Pydantic/contract shape stays in `schemas.py`.

## ANTI-PATTERNS
- Do not add heavy orchestration logic directly in `routes/*`.
- Do not bypass `main.py` startup migration flow with ad hoc DB init code.
- Do not place migration logic under `backend/app`; migration revisions belong in `backend/alembic/versions`.
- Do not return oversized AI-only internals from APIs (see `routes/story_logs.py` comment on judgments payload).

## COMMANDS
```bash
cd backend && uv run ruff check app
cd backend && uv run pytest tests
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
