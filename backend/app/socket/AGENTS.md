# SOCKET SUBSYSTEM KNOWLEDGE BASE

## OVERVIEW
`backend/app/socket` owns realtime transport and coordination: handlers parse events, managers enforce session/presence rules, and server exports the Socket.IO instance.

## STRUCTURE
```text
backend/app/socket/
|- server.py                # sio AsyncServer instance
|- handlers/                # incoming event handlers
|- managers/                # stateful coordination and auth checks
`- utils/                   # socket-only validators/helpers
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Socket server config | `backend/app/socket/server.py` | AsyncServer options and logger |
| Event wiring entry | `backend/app/socket/handlers/*.py` | `join_session`, action submit, AI event triggers |
| Presence/session authority | `backend/app/socket/managers/session_manager.py` and `presence_manager.py` | Host checks, participant counting, lifecycle cleanup |
| Action queue flow | `backend/app/socket/managers/action_queue_manager.py` | Queue state keyed by session |

## CONVENTIONS
- Handler files should focus on event I/O and validation; manager files own shared state transitions.
- Keep authorization checks centralized in managers instead of duplicating guard logic per handler.
- Keep helper logic socket-local in `socket/utils` unless it is broadly reusable.

## ANTI-PATTERNS
- Do not mix long-lived session state mutations directly inside handler functions.
- Do not access database/session state in inconsistent ways across handlers and managers.
- Do not introduce new event names without matching frontend handler registration updates.

## COMMANDS
```bash
cd backend && uv run pytest tests/test_socket_refactoring.py tests/test_participant_management.py tests/test_session_state_manager.py
cd backend && uv run ruff check app/socket
```
