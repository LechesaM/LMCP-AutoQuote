#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8011 >/tmp/lmcp_live_backend.log 2>&1 &
backend_pid=$!
cleanup() {
  kill "$backend_pid" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for _ in $(seq 1 30); do
  if curl -sS --max-time 2 http://127.0.0.1:8011/health -o /tmp/lmcp_live_health.json; then
    break
  fi
  sleep 1
done

python3 - <<'PY'
from app.api.operator_workflow_contracts import get_operator_workflow_http_detail
detail = get_operator_workflow_http_detail("PAPER")
execution = detail.get("submission_execution") or {}
print(execution.get("execution_status"))
PY

python3 - <<'PY'
from app.api.operations_runtime_contracts import build_runtime_metrics_response
from app.api.observability_contracts import build_observability_prometheus_response
from app.api.telemetry_contracts import build_review_queue_telemetry_response
runtime = build_runtime_metrics_response(limit=10)
prom = build_observability_prometheus_response(limit=100)
queue = build_review_queue_telemetry_response(limit=100)
print(runtime.get("status"))
print(prom.get("status"))
print(queue.get("status"))
PY

for _ in $(seq 1 30); do
  if curl -sS --max-time 2 http://127.0.0.1:8011/health -o /tmp/lmcp_live_health_after_prewarm.json; then
    break
  fi
  sleep 1
done

curl -sS --max-time 5 -X POST http://127.0.0.1:8011/auth/login -H "Content-Type: application/json" -d '{"email":"supervisor@lmcp.local","password":"supervisor"}' -o /tmp/lmcp_live_login.json >/dev/null
TOKEN="$(python3 -c 'import json; print(json.load(open("/tmp/lmcp_live_login.json"))["access_token"])')"
export TOKEN

python3 - <<'PY'
import json
import os
import subprocess
import sys

base = "http://127.0.0.1:8011"
token = os.environ["TOKEN"]
headers = ["-H", f"Authorization: Bearer {token}"]
checks = [
    ("PAPER", "/operations/rfqs/PAPER"),
    ("DASHBOARD", "/telemetry/dashboard"),
    ("SOURCE", "/telemetry/source-health"),
    ("QUEUE", "/telemetry/review-queue"),
    ("RUNTIME", "/operations/runtime-metrics?limit=10"),
    ("PROM", "/observability/prometheus"),
    ("UPTIME", "/observability/uptime"),
]
for label, path in checks:
    if path == "/operations/runtime-metrics?limit=10":
        timeout_seconds = "15"
    elif path == "/observability/prometheus":
        timeout_seconds = "10"
    else:
        timeout_seconds = "5"
    result = subprocess.run(["curl", "-sS", "--max-time", timeout_seconds, *headers, base + path], capture_output=True, text=True)
    print(f"{label} rc={result.returncode}")
    if result.returncode != 0:
        print(result.stderr.strip())
        sys.exit(1)
    body = result.stdout
    if path == "/operations/rfqs/PAPER":
        data = json.loads(body)
        print(json.dumps(
            {
                "review_ready": data["review_ready_bundle"]["review_ready"],
                "approval_ready": data["submission_package"]["approval_ready"],
                "submission_ready": data["submission_package"]["submission_ready"],
                "submissionLocked": data["submission_execution"]["submissionLocked"],
                "execution_status": data["submission_execution"]["execution_status"],
                "blockers": data["submission_execution"].get("blockers"),
            },
            indent=2,
        ))
        assert data["review_ready_bundle"]["review_ready"] is True
        assert data["submission_package"]["approval_ready"] is True
        assert data["submission_package"]["submission_ready"] is True
        assert data["submission_execution"]["submissionLocked"] is True
        assert data["submission_execution"]["execution_status"] == "ok"
        assert not data["submission_execution"].get("blockers")
        print("PAPER ok")
    elif path == "/observability/prometheus":
        print(body[:500])
        assert "# HELP" in body and "# TYPE" in body
        print("PROM ok")
    else:
        data = json.loads(body)
        print(json.dumps(
            {
                "status": data.get("status"),
                "data_source": data.get("data_source"),
                "keys": sorted(data.keys())[:20],
            },
            indent=2,
        ))
        assert data.get("status") in {"ok", "degraded", "healthy", "failing"}
        print(f"{label.lower()} {data.get('status')} {data.get('data_source')}")

health = subprocess.run(["curl", "-sS", "--max-time", "5", "http://127.0.0.1:8011/health"], capture_output=True, text=True)
assert health.returncode == 0
health_data = json.loads(health.stdout)
assert health_data["status"] == "healthy"
print("health ok")
PY
