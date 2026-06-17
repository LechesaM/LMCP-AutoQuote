from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.approve_manual_pilot import approve_manual_pilot


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _load_json_object(path: Path, label: str) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object.")
    return payload


def _resolve_optional_manifest_path(pilot_dir: Path, manifest: Dict[str, Any], key: str) -> Optional[str]:
    raw_value = _clean(manifest.get(key))
    if not raw_value:
        return None
    candidate = Path(raw_value).expanduser()
    if not candidate.is_absolute():
        candidate = (pilot_dir / candidate).resolve()
    if not candidate.exists():
        raise FileNotFoundError(f"{key} not found: {candidate}")
    return str(candidate)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Approve a pilot workspace folder using the supervised approval gate.")
    parser.add_argument("--workspace-root", required=True, help="Pilot workspace root containing PILOT-001 etc.")
    parser.add_argument("--pilot-id", required=True, help="Pilot folder name such as PILOT-001.")
    parser.add_argument("--confirm-approval", action="store_true", help="Required confirmation gate.")
    parser.add_argument(
        "--operator-name",
        default="",
        help="Operator name to record in the approval log. Defaults to LMCP_OPERATOR_NAME or Supervisor.",
    )
    parser.add_argument("--instructions-text-file", default=None, help="Optional extracted instructions or tender text.")
    args = parser.parse_args(argv)

    workspace_root = Path(args.workspace_root).expanduser().resolve()
    pilot_dir = workspace_root / args.pilot_id
    if not pilot_dir.exists():
        print(f"Pilot folder not found: {pilot_dir}", file=sys.stderr)
        return 2

    status = _load_json_object(pilot_dir / "submission_logs" / "pilot_status.json", "pilot_status.json")
    manifest = _load_json_object(pilot_dir / "pilot_manifest.json", "pilot_manifest.json")

    tender_id = _clean(status.get("rfq_number") or status.get("tender_id") or args.pilot_id)
    tender_root = pilot_dir / "rfq_source"
    if not tender_root.exists():
        print(f"RFQ source folder not found: {tender_root}", file=sys.stderr)
        return 2

    pricing_file = _clean(manifest.get("pricing_file"))
    if not pricing_file:
        print("pilot_manifest.json must include a pricing_file for approval.", file=sys.stderr)
        return 2
    pricing_file = _resolve_optional_manifest_path(pilot_dir, manifest, "pricing_file") or pricing_file
    operator_name = _clean(args.operator_name) or _clean(os.getenv("LMCP_OPERATOR_NAME")) or "Supervisor"

    outcome = approve_manual_pilot(
        tender_root=str(tender_root),
        tender_id=tender_id,
        pricing_file=pricing_file,
        confirm_approval=args.confirm_approval,
        operator_name=operator_name,
        instructions_text=Path(args.instructions_text_file).read_text(encoding="utf-8") if args.instructions_text_file else None,
        workspace_root=str(workspace_root),
        workspace_pilot_id=args.pilot_id,
    )

    if outcome.get("status") == "recorded":
        pilot_status_path = pilot_dir / "submission_logs" / "pilot_status.json"
        if pilot_status_path.exists():
            status_payload = _load_json_object(pilot_status_path, "pilot_status.json")
            status_payload["status"] = "approved"
            status_payload["submission_ready"] = True
            status_payload["latest_run"] = {
                "status": "approved",
                "quote_pack_quality_status": (outcome.get("result") or {}).get("quote_pack_quality_status", ""),
                "approval_blocked": bool((outcome.get("result") or {}).get("approval_blocked", False)),
                "submission_ready": True,
                "blocker": "",
            }
            pilot_status_path.write_text(json.dumps(status_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(
        {
            "pilot_id": args.pilot_id,
            "tender_id": tender_id,
            "status": outcome.get("status"),
            "reason": outcome.get("reason", ""),
            "gate": outcome.get("gate", {}),
            "submission_ready": bool((outcome.get("approval_record") or {}).get("submission_ready", False)),
            "manual_approval_recorded": bool((outcome.get("approval_record") or {}).get("manual_approval_recorded", False)),
            "operator_name": operator_name,
        },
        indent=2,
        sort_keys=True,
        default=str,
    ))
    return 0 if outcome.get("status") == "recorded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
