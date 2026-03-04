# PROJECT KNOWLEDGE BASE

**Generated:** 2026-03-03 18:30:29 KST
**Commit:** c31f7b6
**Branch:** main

## OVERVIEW
TRPG World is a split-stack repository: FastAPI backend for API + Socket.IO game runtime, and React + TypeScript frontend for the live TRPG UI. E2E verification is Docker-first and Playwright-driven from `scripts/e2e`.

## STRUCTURE
```text
trpg-world/
|- backend/                 # FastAPI app, DB migrations, tests, backend scripts
|  |- app/                  # Runtime code: routes, services, socket, prompts
|  |- tests/                # Pytest suites (API, services, socket behavior)
|  `- scripts/              # Data reset, diagnostics, migration helpers
|- frontend/
|  `- src/                  # React app, stores, socket event handlers
|- scripts/e2e/             # Docker + Playwright end-to-end runner
|- docs/                    # Product and technical documentation
`- docker-compose.yml       # Local/prod-like multi-service orchestration
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Backend app bootstrap | `backend/app/main.py` | FastAPI startup, migrations, router registration, Socket.IO ASGI app export |
| HTTP API surface | `backend/app/routes/` | Route modules by domain (`auth`, `sessions`, `characters`, `story_logs`, `llm_settings`) |
| Real-time server flow | `backend/app/socket/` | `handlers/` receives events, `managers/` coordinates session/presence/action queue |
| AI orchestration | `backend/app/services/` and `backend/app/services/ai_nodes/` | Story director + node pipeline |
| Frontend app bootstrap | `frontend/src/main.tsx` and `frontend/src/App.tsx` | Root render + screen routing/state handoff |
| Frontend real-time events | `frontend/src/stores/socket-handlers/` | Domain handlers registered via `index.ts` |
| Integration tests | `backend/tests/` | Pytest with in-memory SQLite and dependency override patterns |
| End-to-end regression | `scripts/e2e/` | Compose up/reset + Playwright runner in Docker |

## CODE MAP
| Symbol | Type | Location | Refs | Role |
|--------|------|----------|------|------|
| `on_startup` | function | `backend/app/main.py` | medium | Startup migrations + active LLM config sync |
| `run_startup_migrations` | function | `backend/app/main.py` | low | Alembic upgrade to `head` before serving |
| `router` | APIRouter | `backend/app/routes/*.py` | high | Domain API boundaries by module |
| `sio` | socket server | `backend/app/socket/server.py` | high | Core AsyncServer instance |
| `registerAllSocketHandlers` | function | `frontend/src/stores/socket-handlers/index.ts` | medium | Client-side event registration fan-out |

## CONVENTIONS
- Backend package manager/build uses `uv` + Hatch (`pyproject.toml`); Python target is 3.11.
- Backend lint/format authority is Ruff (`backend/ruff.toml`), 120-char line width, first-party package `app`.
- Frontend production build is strict two-step: `tsc -b && vite build` (type-check before bundling).
- Frontend dev server proxies `/api` and `/socket.io` to backend in `frontend/vite.config.ts`.
- Frontend real-time logic is split: socket transport in `stores/socketStore.ts`, domain event handlers in `stores/socket-handlers/`.
- E2E path is script-driven (no `.github/workflows` in repo): compose up, reset state, run Playwright in Docker.
- Runtime orchestration rule: start/restart backend and frontend with `docker compose` (not ad-hoc local `uvicorn` for normal operation).

## ANTI-PATTERNS (THIS PROJECT)
- Do not bypass typed build gate by shipping frontend changes that only pass Vite but fail `tsc -b`.
- Do not couple socket handlers and managers ad hoc; keep event I/O in `handlers/`, coordination/state rules in `managers/`.
- Do not add API response payload bloat that violates route-level contracts (example comment in `backend/app/routes/story_logs.py`).
- Do not treat migration scripts as app runtime modules; Alembic revisions live under `backend/alembic/versions` and follow migration-only scope.
- Do not rely on hidden operational files (`.openclaw`, `.kiro`) as source-of-truth for runtime behavior.

## UNIQUE STYLES
- AI gameplay flow is explicitly staged (judgment -> dice -> narrative) and appears in both backend services and UI messaging.
- Backend keeps a compatibility wrapper `backend/app/socket_server.py` that re-exports socket internals.
- Tests prefer fixture-driven app/database setup with in-memory SQLite + `dependency_overrides` for API route tests.

## COMMANDS
```bash
# backend
cd backend && uv sync
cd backend && uv run ruff check .
cd backend && uv run pytest

# frontend
cd frontend && npm install
cd frontend && npm run dev
cd frontend && npm run build
cd frontend && npm run lint

# docker compose runtime (preferred)
docker compose up -d --build backend
docker compose up -d --build frontend
docker compose up -d --build
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend

# e2e
docker compose up -d --build
./scripts/e2e/setup-and-run.sh
```

## NOTES
- Root-level AGENTS guidance is intentionally lean; detailed subsystem constraints live in child AGENTS files.
- Prioritize child AGENTS docs for: `backend/app`, `backend/app/socket`, `frontend/src`, `frontend/src/stores/socket-handlers`, `backend/tests`, `scripts/e2e`, `docs`.
- If service restart is requested, use `docker compose up -d --build <service>` first.
