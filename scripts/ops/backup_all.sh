#!/usr/bin/env bash
set -euo pipefail

STAMP="${1:-$(date +%Y%m%d_%H%M%S)}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RUNTIME_DIR="$(bash "$SCRIPT_DIR/backup_runtime.sh" "$STAMP")"
DATABASE_DIR="$(bash "$SCRIPT_DIR/backup_database.sh" "$STAMP")"

printf '%s\n%s\n' "$RUNTIME_DIR" "$DATABASE_DIR"
