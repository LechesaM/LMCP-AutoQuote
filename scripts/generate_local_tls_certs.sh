#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_DIR="${LMCP_TLS_CERT_DIR:-$ROOT/runtime/certs}"
CERT_PATH="${CERT_DIR}/lmcp.crt"
KEY_PATH="${CERT_DIR}/lmcp.key"

mkdir -p "$CERT_DIR"

if [[ -f "$CERT_PATH" && -f "$KEY_PATH" ]]; then
  echo "TLS certs already exist at $CERT_DIR"
  exit 0
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl is required to generate local TLS certificates" >&2
  exit 1
fi

openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
  -keyout "$KEY_PATH" \
  -out "$CERT_PATH" \
  -subj "/CN=localhost"

chmod 600 "$KEY_PATH"
echo "Generated local TLS certificate at $CERT_PATH"
