from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_manual_pilot import run_manual_pilot


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _load_pilot_status(pilot_dir: Path) -> Dict[str, Any]:
    status_path = pilot_dir / "submission_logs" / "pilot_status.json"
    if not status_path.exists():
        raise FileNotFoundError(f"Pilot status file not found: {status_path}")
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("pilot_status.json must contain a JSON object.")
    return payload


def _load_pilot_manifest(pilot_dir: Path) -> Dict[str, Any]:
    manifest_path = pilot_dir / "pilot_manifest.json"
    if not manifest_path.exists():
        return {}
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("pilot_manifest.json must contain a JSON object.")
    return payload


def _load_optional_text(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    text_path = Path(path).expanduser()
    if not text_path.exists():
        raise FileNotFoundError(f"Instructions text file not found: {text_path}")
    return text_path.read_text(encoding="utf-8")


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
    parser = argparse.ArgumentParser(description="Run a pilot workspace folder through the manual dry-run pipeline.")
    parser.add_argument("--workspace-root", required=True, help="Pilot workspace root containing PILOT-001 etc.")
    parser.add_argument("--pilot-id", required=True, help="Pilot folder name such as PILOT-001.")
    parser.add_argument("--pricing-file", default=None, help="Optional pricing JSON file to pass to the dry-run pipeline.")
    parser.add_argument("--instructions-text-file", default=None, help="Optional text file to use as tender instructions.")
    args = parser.parse_args(argv)

    workspace_root = Path(args.workspace_root).expanduser().resolve()
    pilot_dir = workspace_root / args.pilot_id
    if not pilot_dir.exists():
        print(f"Pilot folder not found: {pilot_dir}", file=sys.stderr)
        return 2

    pilot_status = _load_pilot_status(pilot_dir)
    pilot_manifest = _load_pilot_manifest(pilot_dir)
    tender_id = _clean(pilot_status.get("rfq_number") or pilot_status.get("tender_id") or args.pilot_id)
    tender_root = pilot_dir / "rfq_source"
    if not tender_root.exists():
        print(f"RFQ source folder not found: {tender_root}", file=sys.stderr)
        return 2
    pricing_file = _clean(args.pricing_file)
    if not pricing_file:
        pricing_file = _resolve_optional_manifest_path(pilot_dir, pilot_manifest, "pricing_file") or ""

    result = run_manual_pilot(
        tender_root=str(tender_root),
        tender_id=tender_id,
        instructions_text=_load_optional_text(args.instructions_text_file),
        pricing_file=pricing_file or None,
        workspace_root=str(workspace_root),
        workspace_pilot_id=args.pilot_id,
    )

    print(json.dumps(
        {
            "pilot_id": args.pilot_id,
            "tender_id": tender_id,
            "pilot_scope": pilot_manifest.get("pilot_scope", []),
            "success_criteria": pilot_manifest.get("success_criteria", []),
            "status": result.get("status"),
            "submission_ready": bool(result.get("submission_ready", False)),
            "quote_pack_quality_status": result.get("quote_pack_quality_status"),
            "approval_blocked": bool(result.get("approval_blocked", False)),
            "workspace_log": str(tender_root.parent / "submission_logs" / "live_run_log.md"),
        },
        indent=2,
        sort_keys=True,
        default=str,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
