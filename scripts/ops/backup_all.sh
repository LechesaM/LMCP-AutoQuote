#!/usr/bin/env bash
set -euo pipefail

STAMP="${1:-$(date +%Y%m%d_%H%M%S)}"
RUNTIME_DIR="$(bash scripts/ops/backup_runtime.sh "$STAMP")"
DATABASE_DIR="$(bash scripts/ops/backup_database.sh "$STAMP")"

printf '%s\n%s\n' "$RUNTIME_DIR" "$DATABASE_DIR"
