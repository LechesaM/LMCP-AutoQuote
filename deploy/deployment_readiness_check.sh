#!/usr/bin/env bash
set -e

echo "LMCP Deployment Readiness Check"
echo "=============================="

cd /Users/Shared/LMCP-AutoQuote-Server

echo ""
echo "1) Docker services:"
docker compose ps

echo ""
echo "2) Backend health:"
curl -s http://localhost:8000/health | python3 -m json.tool | head -80

echo ""
echo "3) Submission history with proofs:"
curl -s http://localhost:8000/submission-history/recent-with-proofs | python3 -m json.tool | head -120

echo ""
echo "4) V48 policy:"
curl -s http://localhost:8000/v48-autonomous/status | python3 -m json.tool || true

echo ""
echo "5) Portal status:"
curl -s http://localhost:8000/portal-submission/status | python3 -m json.tool || true

echo ""
echo "6) Frontend folder:"
test -f lmcp-frontend/package.json && echo "OK: lmcp-frontend/package.json exists" || echo "WARNING: frontend package.json missing"

echo ""
echo "DONE: Review warnings above before 24/7 deployment."
