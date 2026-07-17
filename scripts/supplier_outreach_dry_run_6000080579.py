#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.supplier_outreach_service import write_supplier_outreach_dry_run


DEFAULT_REQUIREMENT_PACK = Path("/tmp/lmcp-reprocess-6000080579/outputs/rfq_requirement_pack.json")
DEFAULT_PRICING_WORKSPACE = Path("/tmp/lmcp-pricing-workspace-6000080579/outputs/pricing_workspace_result.json")
DEFAULT_OUTPUT = Path("/tmp/lmcp-supplier-outreach-6000080579/outputs")
PRODUCTION_RUNTIME = (REPO_ROOT / "runtime").resolve()
SAFE_TMP_PREFIX = Path("/tmp").resolve()


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_output_dir(path: Path) -> Path:
    resolved = path.resolve()
    if resolved == PRODUCTION_RUNTIME or PRODUCTION_RUNTIME in resolved.parents:
        raise SystemExit(f"Refusing production runtime output path: {resolved}")
    if resolved != SAFE_TMP_PREFIX and SAFE_TMP_PREFIX not in resolved.parents:
        raise SystemExit(f"Refusing non-temporary output path: {resolved}")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run supplier outreach validation for RFQ 6000080579.")
    parser.add_argument("--requirement-pack", default=str(DEFAULT_REQUIREMENT_PACK))
    parser.add_argument("--pricing-workspace-result", default=str(DEFAULT_PRICING_WORKSPACE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    output_dir = _safe_output_dir(Path(args.output))
    requirement_pack = _read_json(Path(args.requirement_pack))
    pricing_workspace_result = _read_json(Path(args.pricing_workspace_result))
    result = write_supplier_outreach_dry_run(
        requirement_pack=requirement_pack,
        pricing_workspace_result=pricing_workspace_result,
        output_dir=output_dir,
    )
    print(json.dumps({
        "status": result.get("status"),
        "request_id": result.get("request_id"),
        "supplier_count": len(result.get("suppliers") or []),
        "email_models": len(result.get("email_models") or []),
        "followup_schedules": len(result.get("followup_schedules") or []),
        "supplier_quote_coverage": (result.get("no_response_pricing_state") or {}).get("supplier_quote_coverage"),
        "pricing_ready": (result.get("no_response_pricing_state") or {}).get("pricing_ready"),
    }, indent=2))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
