# BACKEND TESTS KNOWLEDGE BASE

## OVERVIEW
`backend/tests` is a pytest suite focused on API routes, service behavior, and socket/session coordination.

## STRUCTURE
```text
backend/tests/
|- test_routes_*.py          # API contracts and validation
|- test_*_node.py            # AI node behavior
|- test_*_manager.py         # session/task manager logic
`- test_socket_*.py          # realtime flow checks
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Route contract tests | `backend/tests/test_routes_sessions.py` and `test_routes_characters.py` | FastAPI `TestClient` + dependency override patterns |
| AI node tests | `backend/tests/test_judgment_node.py` and `test_narrative_node.py` | Staged AI behavior checks |
| State/queue tests | `backend/tests/test_session_state_manager.py` and `test_background_task_manager.py` | Session state and async task behavior |
| Socket-focused tests | `backend/tests/test_socket_refactoring.py` and `test_participant_management.py` | Realtime coordination invariants |

## CONVENTIONS
- Use in-memory SQLite (`sqlite:///:memory:` + `StaticPool`) for isolated route tests.
- Prefer fixture-driven setup for engine/session/app/client composition.
- Use `dependency_overrides` for route tests instead of patching internals ad hoc.

## ANTI-PATTERNS
- Do not couple tests to external services or network side effects.
- Do not bypass fixtures with shared mutable globals between tests.
- Do not rewrite assertions to depend on unstable prompt wording when behavior-level checks are possible.

## COMMANDS
```bash
cd backend && uv run pytest
cd backend && uv run pytest tests/test_routes_sessions.py tests/test_routes_characters.py
```
