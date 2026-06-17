#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${LMCP_PROJECT_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$PROJECT_ROOT"

BACKUP_ROOT="${LMCP_BACKUP_DIR:-$PWD/backups/production}"
STAMP="${1:-$(date +%Y%m%d_%H%M%S)}"
OUT_DIR="$BACKUP_ROOT/$STAMP"
OUT_FILE="$OUT_DIR/database.sql.gz"

mkdir -p "$OUT_DIR"

DATABASE_URL_VALUE="${DATABASE_URL:-${LMCP_DATABASE_URL:-}}"

PG_DUMP_BIN="${LMCP_PG_DUMP_BIN:-}"

docker_ready() {
  command -v docker >/dev/null 2>&1 || return 1
  docker compose version >/dev/null 2>&1 || return 1
  python3 - <<'PY'
import subprocess
import sys

try:
    subprocess.run(
        ["docker", "info"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5,
    )
except Exception:
    sys.exit(1)
PY
}

set_pg_env_from_url() {
  local url="$1"
  if [[ -z "$url" ]]; then
    return 1
  fi

  eval "$(python3 - "$url" <<'PY'
import sys
from urllib.parse import unquote, urlparse

url = sys.argv[1]
parsed = urlparse(url)
print(f'export PGHOST="{parsed.hostname or ""}"')
print(f'export PGPORT="{parsed.port or 5432}"')
print(f'export PGDATABASE="{parsed.path.lstrip("/")}"')
print(f'export PGUSER="{unquote(parsed.username or "")}"')
print(f'export PGPASSWORD="{unquote(parsed.password or "")}"')
PY
)"
}

run_docker_backup() {
  docker compose exec -T db sh -lc 'export PGPASSWORD="${POSTGRES_PASSWORD:-}"; pg_dump -U "${POSTGRES_USER:-lmcp}" -d "${POSTGRES_DB:-lmcp_autoquote}" --format=plain --no-owner --no-privileges' | gzip -c > "$OUT_FILE"
}

run_local_backup() {
  local candidate=""
  if [[ -n "$PG_DUMP_BIN" && -x "$PG_DUMP_BIN" ]]; then
    candidate="$PG_DUMP_BIN"
  elif command -v pg_dump >/dev/null 2>&1; then
    candidate="$(command -v pg_dump)"
  elif [[ -x /opt/homebrew/opt/libpq/bin/pg_dump ]]; then
    candidate="/opt/homebrew/opt/libpq/bin/pg_dump"
  elif [[ -x /usr/local/opt/libpq/bin/pg_dump ]]; then
    candidate="/usr/local/opt/libpq/bin/pg_dump"
  else
    return 1
  fi
  if ! set_pg_env_from_url "$DATABASE_URL_VALUE"; then
    return 1
  fi
  "$candidate" --format=plain --no-owner --no-privileges | gzip -c > "$OUT_FILE"
}

if docker_ready; then
  if ! run_docker_backup; then
    if run_local_backup; then
      :
    else
      echo "Database backup failed using Docker and local pg_dump. This script is PostgreSQL-only: ensure the Docker daemon is running with the postgres service, or set DATABASE_URL/LMCP_DATABASE_URL and install pg_dump locally." >&2
      exit 1
    fi
  fi
elif run_local_backup; then
  :
else
  echo "Database backup requires a ready Docker daemon with the postgres service or local pg_dump plus DATABASE_URL/LMCP_DATABASE_URL. This script backs up PostgreSQL only." >&2
  echo "Remediation: start Docker Desktop and the postgres service, or install pg_dump and export DATABASE_URL/LMCP_DATABASE_URL for a reachable PostgreSQL instance." >&2
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
