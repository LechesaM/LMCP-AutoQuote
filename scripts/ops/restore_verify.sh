#!/usr/bin/env bash
set -euo pipefail

cd /Users/Shared/LMCP-AutoQuote-Server

BUNDLE_DIR="${1:-}"
if [[ -z "$BUNDLE_DIR" ]]; then
  echo "Usage: scripts/ops/restore_verify.sh /path/to/backups/production/<timestamp>" >&2
  exit 1
fi

RUNTIME_ARCHIVE="$BUNDLE_DIR/runtime_bundle.tar.gz"
DB_ARCHIVE="$BUNDLE_DIR/database.sql.gz"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

if [[ ! -f "$RUNTIME_ARCHIVE" ]]; then
  echo "Missing runtime archive: $RUNTIME_ARCHIVE" >&2
  exit 1
fi

tar -xzf "$RUNTIME_ARCHIVE" -C "$TMP_DIR"

for required in \
  "$TMP_DIR/runtime" \
  "$TMP_DIR/runtime/live_buyer_packs" \
  "$TMP_DIR/runtime/quote_compilation" \
  "$TMP_DIR/runtime/submission_proofs" \
  "$TMP_DIR/runtime/rfq_lifecycle" \
  "$TMP_DIR/runtime/proof_center" \
  "$TMP_DIR/runtime/manual_pricing" \
  "$TMP_DIR/runtime/operator_actions" \
  "$TMP_DIR/runtime/audit_trail" \
  "$TMP_DIR/runtime/logs"
do
  if [[ ! -e "$required" ]]; then
    echo "Restore verification failed: missing $required" >&2
    exit 1
  fi
done

python3 - <<PY
import json
from pathlib import Path
runtime = Path("$TMP_DIR") / "runtime" / "live_rfqs.json"
if runtime.exists():
    data = json.loads(runtime.read_text())
    assert isinstance(data, dict), "runtime/live_rfqs.json must be a JSON object"
    assert isinstance(data.get("items"), list), "runtime/live_rfqs.json must contain an items list"
print("runtime backup structure validated")
PY

if [[ -f "$DB_ARCHIVE" ]]; then
  gzip -t "$DB_ARCHIVE"
fi

python3 - <<'PY'
from app.main import health
payload = health()
assert payload.get("status") == "healthy", payload
print("application import and health check passed")
PY

echo "Restore verification succeeded for $BUNDLE_DIR"
