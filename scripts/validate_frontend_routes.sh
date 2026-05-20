#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

echo "[cutover] Frontend route validation"

python3 -B - <<'PY'
from pathlib import Path
import re

app_path = Path("frontend/command-centre/src/App.jsx")
routes_path = Path("frontend/command-centre/src/routes/commandCentreRoutes.ts")

required_routes = [
    "/dashboard",
    "/operations",
    "/review",
    "/governance",
    "/source-health",
    "/qualification-insights",
    "/pricing-evidence",
    "/operator-operations",
    "/operator-productivity",
    "/executive-dashboard",
    "/observability",
    "/stabilization-operations",
]

app_text = app_path.read_text(encoding="utf-8")
routes_text = routes_path.read_text(encoding="utf-8")
missing = [route for route in required_routes if route not in app_text or route not in routes_text]

print(f"app_routes_checked: {app_path}")
print(f"route_registry_checked: {routes_path}")
print(f"required_route_count: {len(required_routes)}")
print(f"missing_route_count: {len(missing)}")
for route in missing:
    print(f"missing_route: {route}")

route_count = len(re.findall(r"path:\s*\"/[^\"]+\"", routes_text))
print(f"declared_route_count: {route_count}")

raise SystemExit(0 if not missing else 1)
PY
