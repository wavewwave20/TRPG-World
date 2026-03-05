# FRONTEND SOCKET HANDLERS KNOWLEDGE BASE

## OVERVIEW
This directory is the client-side event ingestion layer. It converts server socket events into deterministic Zustand state updates.

## STRUCTURE
```text
frontend/src/stores/socket-handlers/
|- index.ts                  # all-domain registration point
|- sessionHandlers.ts        # session and participant events
|- judgmentHandlers.ts       # judgment lifecycle events
|- narrativeHandlers.ts      # narrative_stream_* / narrative_* events
`- actHandlers.ts            # action queue/moderation events
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Registration fan-out | `frontend/src/stores/socket-handlers/index.ts` | `registerAllSocketHandlers(socket)` is single entry |
| Session lifecycle events | `frontend/src/stores/socket-handlers/sessionHandlers.ts` | Join/leave/session status updates |
| Judgment phase events | `frontend/src/stores/socket-handlers/judgmentHandlers.ts` | Analysis/judgment transitions |
| Narrative and streaming events | `frontend/src/stores/socket-handlers/narrativeHandlers.ts` | Story generation and output updates |
| Action/act events | `frontend/src/stores/socket-handlers/actHandlers.ts` | Action moderation and queue updates |

## CONVENTIONS
- Add new event logic in a domain handler file, then register it in `index.ts`.
- Keep handlers thin and deterministic: parse payload, dispatch store updates, avoid hidden async side effects.
- Reuse store actions/selectors instead of mutating state ad hoc across handler files.

## ANTI-PATTERNS
- Do not register handlers directly in UI components.
- Do not duplicate event names across modules with conflicting behavior.
- Do not introduce server event handling here without matching backend emitter contract.

## COMMANDS
```bash
cd frontend && npm run build
cd frontend && npm run lint
```
