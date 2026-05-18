#!/usr/bin/env bash
set -euo pipefail

cd /Users/Shared/LMCP-AutoQuote-Server

BACKUP_ROOT="${LMCP_BACKUP_DIR:-$PWD/backups/production}"
STAMP="${1:-$(date +%Y%m%d_%H%M%S)}"
OUT_DIR="$BACKUP_ROOT/$STAMP"
ARCHIVE="$OUT_DIR/runtime_bundle.tar.gz"

mkdir -p "$OUT_DIR"

tar -czf "$ARCHIVE" \
  runtime/live_buyer_packs \
  runtime/quote_compilation \
  runtime/submission_proofs \
  runtime/rfq_lifecycle \
  runtime/proof_center \
  runtime/manual_pricing \
  runtime/operator_actions \
  runtime/audit_trail \
  runtime/logs

cat > "$OUT_DIR/backup_manifest.json" <<EOF
{
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "project_root": "$PWD",
  "archive": "$ARCHIVE",
  "includes": [
    "runtime/live_buyer_packs",
    "runtime/quote_compilation",
    "runtime/submission_proofs",
    "runtime/rfq_lifecycle",
    "runtime/proof_center",
    "runtime/manual_pricing",
    "runtime/operator_actions",
    "runtime/audit_trail",
    "runtime/logs"
  ]
}
EOF

echo "$OUT_DIR"
