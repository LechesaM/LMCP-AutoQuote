#!/bin/bash

PROJECT_ROOT="/Users/Shared/LMCP-AutoQuote-Server"

echo "=========================================="
echo "Stopping LMCP AutoQuote System"
echo "Project root: $PROJECT_ROOT"
echo "=========================================="

cd "$PROJECT_ROOT" || {
  echo "ERROR: Project root not found: $PROJECT_ROOT"
  exit 1
}

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker is not installed or not in PATH."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop does not appear to be running."
  echo "Nothing to stop through docker compose."
  exit 0
fi

docker compose down

if [ $? -ne 0 ]; then
  echo "ERROR: Failed to stop LMCP AutoQuote cleanly."
  exit 1
fi

echo ""
echo "LMCP AutoQuote stopped successfully."
