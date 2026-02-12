#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNNER_PATH="$ROOT_DIR/scripts/e2e/trpg-e2e-runner.js"
BASE_URL="${BASE_URL:-http://localhost:5173}"
OUT_FILE="${1:-/tmp/trpg-e2e-result-$(date +%Y%m%d-%H%M%S).log}"

cd "$ROOT_DIR"

if [[ ! -f "$RUNNER_PATH" ]]; then
  echo "runner not found: $RUNNER_PATH" >&2
  exit 1
fi

echo "[E2E] BASE_URL=$BASE_URL"
echo "[E2E] OUT_FILE=$OUT_FILE"

docker run --rm --network host \
  -e BASE_URL="$BASE_URL" \
  -v "$RUNNER_PATH:/work/run.js" \
  -w /work \
  mcr.microsoft.com/playwright:v1.58.2-noble \
  bash -lc "npm init -y >/dev/null 2>&1 && npm i playwright >/dev/null 2>&1 && PLAYWRIGHT_BROWSERS_PATH=/ms-playwright node run.js" \
  | tee "$OUT_FILE"

echo "[E2E] done"
