# E2E SCRIPTS KNOWLEDGE BASE

## OVERVIEW
`scripts/e2e` provides the dockerized end-to-end verification path. It builds services, resets test state, and runs Playwright scenarios in a container.

## STRUCTURE
```text
scripts/e2e/
|- setup-and-run.sh         # full cycle: build -> up -> reset -> run
|- reset-test-state.sh      # DB cleanup/reset before runs
|- run-e2e-docker.sh        # Playwright container launcher
`- trpg-e2e-runner.js       # scenario matrix and checks
```

## CONVENTIONS
- Treat `setup-and-run.sh` as the canonical full-stack E2E entrypoint.
- `run-e2e-docker.sh` uses host networking and Playwright image to hit local services.
- Scenario matrix is declared in `trpg-e2e-runner.js`; status output is PASS/FAIL/BLOCKED per scenario.

## ANTI-PATTERNS
- Do not run E2E against stale state; use reset script before assertions.
- Do not add scenario IDs in docs only; keep runner source as the matrix of truth.
- Do not assume CI workflow files exist; this repo uses script-driven E2E orchestration.

## COMMANDS
```bash
./scripts/e2e/setup-and-run.sh
./scripts/e2e/reset-test-state.sh
./scripts/e2e/run-e2e-docker.sh
```
