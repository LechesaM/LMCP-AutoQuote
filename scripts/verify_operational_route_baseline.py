#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPOSITORY = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPOSITORY / "config" / "lmcp_v2_operational_route_baseline.json"

if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def method_path_pairs(openapi: Dict[str, Any]) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for path, operations in sorted((openapi.get("paths") or {}).items()):
        if not isinstance(operations, dict):
            continue
        for method in operations:
            upper = str(method).upper()
            if upper in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                pairs.append((upper, path))
    return pairs


def has_prefix(paths: List[str], prefix: str) -> bool:
    if prefix == "/":
        return "/" in paths
    return any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for path in paths)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify LMCP v2 operational route baseline.")
    parser.add_argument("--baseline", default=str(BASELINE_PATH))
    parser.add_argument("--output")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    baseline = load_json(baseline_path)

    from app.main import app, disabled_routers, failed_routers, loaded_routers
    from app.core.router_activation import DISABLED_BY_DEFAULT

    openapi = app.openapi()
    pairs = method_path_pairs(openapi)
    pair_counts = Counter(pairs)
    duplicate_pairs = [
        {"method": method, "path": path, "count": count}
        for (method, path), count in sorted(pair_counts.items())
        if count > 1
    ]
    paths = sorted((openapi.get("paths") or {}).keys())

    missing_required: List[Dict[str, Any]] = []
    enabled_disabled_by_default: List[Dict[str, Any]] = []
    high_risk_without_controls: List[Dict[str, Any]] = []
    family_results: List[Dict[str, Any]] = []

    controlled_statuses = {
        "DISABLED_BY_DEFAULT",
        "ENABLED_CONTROLLED",
        "REQUIRES_OPERATOR_APPROVAL",
        "RETIRED",
        "EXPERIMENTAL",
    }

    for family in baseline.get("families", []):
        status = str(family.get("status") or "")
        prefixes = [str(prefix) for prefix in family.get("route_prefixes") or []]
        present_prefixes = [prefix for prefix in prefixes if has_prefix(paths, prefix)]
        missing_prefixes = [prefix for prefix in prefixes if prefix not in present_prefixes]
        result = {
            "family": family.get("family"),
            "status": status,
            "route_prefixes": prefixes,
            "present_prefixes": present_prefixes,
            "missing_prefixes": missing_prefixes,
            "safety_level": family.get("safety_level"),
            "feature_gate": family.get("feature_gate"),
        }
        family_results.append(result)

        if status in {"REQUIRED", "REQUIRED_COMPATIBILITY"} and missing_prefixes:
            missing_required.append(result)

        if status in {"DISABLED_BY_DEFAULT", "RETIRED"} and present_prefixes:
            enabled_disabled_by_default.append(result)

        if str(family.get("safety_level") or "").upper() in {"HIGH", "CRITICAL"} and status not in controlled_statuses:
            high_risk_without_controls.append(result)

    disabled_router_names = [name for name, _reason in disabled_routers]
    missing_disabled_router_controls = sorted(set(DISABLED_BY_DEFAULT) - set(disabled_router_names))

    report = {
        "generated_at": utc_now(),
        "repository": str(REPOSITORY),
        "baseline": str(baseline_path),
        "loaded_router_count": len(loaded_routers),
        "failed_router_count": len(failed_routers),
        "disabled_router_count": len(disabled_routers),
        "method_path_count": len(pairs),
        "path_count": len(paths),
        "duplicate_route_count": len(duplicate_pairs),
        "duplicate_routes": duplicate_pairs,
        "missing_required": missing_required,
        "enabled_disabled_by_default": enabled_disabled_by_default,
        "high_risk_without_controls": high_risk_without_controls,
        "disabled_by_default_routers": disabled_router_names,
        "missing_disabled_router_controls": missing_disabled_router_controls,
        "family_results": family_results,
        "passed": not missing_required and not enabled_disabled_by_default and not high_risk_without_controls and not duplicate_pairs and len(failed_routers) == 0,
    }

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.verbose:
        print(json.dumps({k: report[k] for k in [
            "loaded_router_count",
            "failed_router_count",
            "disabled_router_count",
            "method_path_count",
            "duplicate_route_count",
            "missing_required",
            "enabled_disabled_by_default",
            "high_risk_without_controls",
            "passed",
        ]}, indent=2, sort_keys=True))

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
