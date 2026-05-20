#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
URL=${LMCP_HIT_TEST_URL:-http://127.0.0.1:4173/__debug/hit-test}

if node -e "import('playwright').then(() => process.exit(0)).catch(() => process.exit(1))" >/dev/null 2>&1; then
  LMCP_HIT_TEST_URL="$URL" node "$SCRIPT_DIR/confirm_sidebar_hit_test.mjs"
  exit $?
fi

printf '%s\n' '{"status":"playwright_missing","url":"'"$URL"'","message":"Open the debug hit-test page in a browser and inspect elementFromPoint results manually."}'
exit 0
