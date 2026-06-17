#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND_URL="${LMCP_BACKEND_URL:-http://127.0.0.1:8011}"
TOKEN="${LMCP_ADMIN_ACCESS_TOKEN:-${LMCP_ACCESS_TOKEN:-}}"

if [[ -z "${TOKEN}" ]]; then
  if [[ -n "${LMCP_ADMIN_EMAIL:-}" && -n "${LMCP_ADMIN_PASSWORD:-}" ]]; then
    LOGIN_RESPONSE="$(curl -sS --max-time 10 -X POST "${BACKEND_URL}/auth/login" -H 'Content-Type: application/json' -d "{\"email\":\"${LMCP_ADMIN_EMAIL}\",\"password\":\"${LMCP_ADMIN_PASSWORD}\"}")"
    TOKEN="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])' <<<"${LOGIN_RESPONSE}")"
  else
    echo "Set LMCP_ADMIN_ACCESS_TOKEN or LMCP_ADMIN_EMAIL/LMCP_ADMIN_PASSWORD before running this script." >&2
    exit 1
  fi
fi

echo "WARNING: This will inject DEMO RFQs into the live runtime store." >&2
echo "DANGER: Demo RFQs are not real procurement opportunities." >&2
echo "Reason must be meaningful (20+ characters) and not 'test'." >&2
echo "Environment: development/local only when LMCP_ALLOW_DEMO_SEED=true" >&2

curl -sS --max-time 10 -X POST "${BACKEND_URL}/admin/demo-seed" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"confirm":"LOAD_DEMO_RFQS","reason":"Manual local demo setup"}' | python3 -m json.tool
