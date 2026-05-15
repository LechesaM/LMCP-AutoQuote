#!/usr/bin/env bash
set -e

cd /Users/Shared/LMCP-AutoQuote-Server

echo "Starting LMCP backend stack..."
docker compose up -d

echo "Waiting for API..."
sleep 8

echo "Health:"
curl -s http://localhost:8000/health | python3 -m json.tool | head -80

echo ""
echo "To start frontend:"
echo "cd /Users/Shared/LMCP-AutoQuote-Server/lmcp-frontend"
echo "npm run dev -- --host 0.0.0.0"
