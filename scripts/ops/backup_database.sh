#!/usr/bin/env bash
set -euo pipefail

cd /Users/Shared/LMCP-AutoQuote-Server

BACKUP_ROOT="${LMCP_BACKUP_DIR:-$PWD/backups/production}"
STAMP="${1:-$(date +%Y%m%d_%H%M%S)}"
OUT_DIR="$BACKUP_ROOT/$STAMP"
OUT_FILE="$OUT_DIR/database.sql.gz"

mkdir -p "$OUT_DIR"

if command -v pg_dump >/dev/null 2>&1; then
  if [[ -n "${DATABASE_URL:-}" ]]; then
    eval "$(python3 - "$DATABASE_URL" <<'PY'
import sys
from urllib.parse import urlparse, unquote
url = sys.argv[1]
parsed = urlparse(url)
print(f'export PGHOST="{parsed.hostname or ""}"')
print(f'export PGPORT="{parsed.port or 5432}"')
print(f'export PGDATABASE="{parsed.path.lstrip("/")}"')
print(f'export PGUSER="{unquote(parsed.username or "")}"')
if parsed.password:
    print(f'export PGPASSWORD="{unquote(parsed.password)}"')
PY
)"
  fi
  pg_dump --format=plain --no-owner --no-privileges | gzip -c > "$OUT_FILE"
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  docker compose exec -T db sh -lc 'export PGPASSWORD="${POSTGRES_PASSWORD:-}"; pg_dump -U "${POSTGRES_USER:-lmcp}" -d "${POSTGRES_DB:-lmcp_autoquote}" --format=plain --no-owner --no-privileges' | gzip -c > "$OUT_FILE"
else
  echo "Database backup requires pg_dump or a Docker daemon with the postgres service available." >&2
  exit 1
fi

cat > "$OUT_DIR/database_backup_manifest.json" <<EOF
{
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "project_root": "$PWD",
  "archive": "$OUT_FILE",
  "database": "${PGDATABASE:-}"
}
EOF

echo "$OUT_DIR"
