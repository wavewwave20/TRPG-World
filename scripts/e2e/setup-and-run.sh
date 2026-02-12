#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$ROOT_DIR"

echo "[E2E] compose build"
docker compose build backend frontend

echo "[E2E] compose up"
docker compose up -d

echo "[E2E] reset test state"
"$ROOT_DIR/scripts/e2e/reset-test-state.sh"

echo "[E2E] run playwright e2e"
if [[ $# -ge 1 && -n "${1}" ]]; then
  "$ROOT_DIR/scripts/e2e/run-e2e-docker.sh" "$1"
else
  "$ROOT_DIR/scripts/e2e/run-e2e-docker.sh"
fi
