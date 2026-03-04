# DOCS KNOWLEDGE BASE

## OVERVIEW
`docs` stores product/spec/verification notes that explain gameplay behavior, optimization decisions, and E2E methodology.

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| E2E execution rationale | `docs/e2e-methodology.md` | Maps scenarios and expected outcomes |
| AI/LLM optimization context | `docs/llm-call-optimization-report.md` | Call-path and performance reasoning |
| Runtime operations notes | `docs/서버실행.md` | Local server run guidance |
| Gameplay validation stories | `docs/test_stories.md` | Scenario-level narrative test content |

## CONVENTIONS
- Keep docs aligned with script and code reality; commands should match runnable repo scripts.
- Prefer focused decision records over broad narrative when documenting technical changes.
- Place visual artifacts in `docs/assets` and keep references relative.

## ANTI-PATTERNS
- Do not document commands that are not present in current scripts/config.
- Do not duplicate full README content inside docs pages; link upstream sections instead.
- Do not let docs drift from E2E runner scenario behavior.

## COMMANDS
```bash
# Link-check style review
grep -RIn "scripts/e2e" docs README.md README.ko.md

# Surface changed docs in git
git status -- docs README.md README.ko.md
```

## NOTES
- `docs/assets` holds screenshot/media artifacts referenced by READMEs and reports.
- Keep bilingual docs aligned (`README.md`, `README.ko.md`) when behavior-level docs change.
