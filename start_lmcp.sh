#!/bin/bash

echo "========================================="
echo "🚀 LMCP AUTOQUOTE SYSTEM STARTING..."
echo "========================================="

# Navigate to project
cd /Users/Shared/LMCP-AutoQuote-Server || exit

# Start Docker Desktop if not running
if ! pgrep -x "Docker" > /dev/null
then
    echo "🐳 Starting Docker Desktop..."
    open -a Docker
    echo "⏳ Waiting for Docker to boot..."
    sleep 15
fi

# Start containers
echo "📦 Starting containers..."
docker compose up -d

# Wait for services
echo "⏳ Waiting for backend to stabilise..."
sleep 10

# Health check
echo "🔍 Checking system health..."
curl -s http://localhost:8000/docs > /dev/null

if [ $? -eq 0 ]; then
    echo "✅ Backend is running"
else
    echo "⚠️ Backend not responding yet (may still be starting)"
fi

# Open dashboards
echo "🌐 Opening dashboards..."
open http://localhost:8000/docs
open http://localhost:5173

echo "========================================="
echo "✅ LMCP AUTOQUOTE SYSTEM IS LIVE"
echo "========================================="
