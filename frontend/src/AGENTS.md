# FRONTEND SRC KNOWLEDGE BASE

## OVERVIEW
`frontend/src` contains the React runtime UI, domain stores, socket event handling, and API client integrations for live TRPG sessions.

## STRUCTURE
```text
frontend/src/
|- main.tsx                 # React root bootstrap
|- App.tsx                  # top-level screen flow
|- components/              # primary UI surfaces (largest area)
|- stores/                  # Zustand state and socket integration
|- services/                # HTTP client and service wrappers
|- types/                   # shared type contracts
`- utils/                   # small pure helpers
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| App bootstrap | `frontend/src/main.tsx` and `frontend/src/App.tsx` | Render root + global flow |
| Session and lobby UI | `frontend/src/components/SessionList.tsx` and `SessionCreationForm.tsx` | Join/create UX |
| Game screen orchestration | `frontend/src/components/GameLayout.tsx` and pane components | Story + actions + participants |
| Network/event state | `frontend/src/stores/socketStore.ts` | Socket connection lifecycle |
| Event domain handling | `frontend/src/stores/socket-handlers/` | Per-domain event reducers/side effects |

## CONVENTIONS
- Keep transport/event processing in stores and socket-handlers; keep components presentation-focused.
- Preserve strict TypeScript gate: `npm run build` must pass `tsc -b` before bundle generation.
- API and socket base routing assumes Vite proxy for `/api` and `/socket.io` during local dev.

## ANTI-PATTERNS
- Do not place websocket side-effect logic directly in many components; centralize in stores/handlers.
- Do not rely on Vite-only success if type-check fails.
- Do not add untyped payload handling in socket paths when shared `types/*` can encode payloads.

## COMMANDS
```bash
cd frontend && npm run lint
cd frontend && npm run build
cd frontend && npm run dev
```
