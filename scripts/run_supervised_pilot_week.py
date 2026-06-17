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

from app.services import manual_approval_service
from app.pilot import record_pilot_run
from scripts import record_manual_submission_proof
from scripts import review_submission_pack
from scripts.run_manual_pilot import run_manual_pilot


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


def _load_optional_text(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    text_path = Path(path).expanduser()
    if not text_path.exists():
        raise FileNotFoundError(f"Instructions text file not found: {text_path}")
    return text_path.read_text(encoding="utf-8")


def _update_pilot_status(pilot_dir: Path, update: Dict[str, Any]) -> None:
    status_path = pilot_dir / "submission_logs" / "pilot_status.json"
    if not status_path.exists():
        return
    status_payload = _load_json_object(status_path, "pilot_status.json")
    status_payload.update(update)
    status_path.write_text(json.dumps(status_payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_summary(
    *,
    pilot_id: str,
    tender_id: str,
    dry_run_result: Dict[str, Any],
    approval_outcome: Dict[str, Any],
    proof_record: Optional[Dict[str, Any]],
    proof_requested: bool,
    next_step: str,
) -> Dict[str, Any]:
    return {
        "pilot_id": pilot_id,
        "tender_id": tender_id,
        "dry_run_status": _clean(dry_run_result.get("status")),
        "quote_pack_quality_status": _clean(dry_run_result.get("quote_pack_quality_status")),
        "approval_blocked": bool(dry_run_result.get("approval_blocked", False)),
        "submission_ready": bool(approval_outcome.get("approval_record", {}).get("submission_ready", False)),
        "manual_approval_recorded": bool(approval_outcome.get("approval_record", {}).get("manual_approval_recorded", False)),
        "approval_status": _clean(approval_outcome.get("status")),
        "approval_reason": _clean(approval_outcome.get("reason")),
        "proof_requested": bool(proof_requested),
        "proof_status": _clean(proof_record.get("status")) if isinstance(proof_record, dict) else "",
        "manual_submission_recorded": bool(proof_record.get("manual_submission_recorded", False)) if isinstance(proof_record, dict) else False,
        "next_step": next_step,
    }


def run_supervised_pilot_week(
    *,
    workspace_root: str,
    pilot_id: str,
    confirm_approval: bool,
    operator_name: str,
    tender_root: Optional[str] = None,
    tender_id: Optional[str] = None,
    pricing_file: Optional[str] = None,
    instructions_text_file: Optional[str] = None,
    portal_name: Optional[str] = None,
    submission_reference: Optional[str] = None,
    proof_file: Optional[str] = None,
    record_proof: bool = False,
) -> Dict[str, Any]:
    workspace_root_path = Path(workspace_root).expanduser().resolve()
    pilot_dir = workspace_root_path / pilot_id
    if not pilot_dir.exists():
        raise FileNotFoundError(f"Pilot folder not found: {pilot_dir}")

    status_path = pilot_dir / "submission_logs" / "pilot_status.json"
    manifest_path = pilot_dir / "pilot_manifest.json"
    status = _load_json_object(status_path, "pilot_status.json") if status_path.exists() else {}
    manifest = _load_json_object(manifest_path, "pilot_manifest.json") if manifest_path.exists() else {}

    resolved_tender_id = _clean(tender_id or status.get("rfq_number") or status.get("tender_id") or pilot_id)
    resolved_tender_root = Path(tender_root).expanduser().resolve() if tender_root else pilot_dir / "rfq_source"
    if not resolved_tender_root.exists():
        raise FileNotFoundError(f"RFQ source folder not found: {resolved_tender_root}")

    resolved_pricing_file = _clean(pricing_file) or _resolve_optional_manifest_path(pilot_dir, manifest, "pricing_file") or ""
    if not resolved_pricing_file:
        raise ValueError("pricing_file is required either as an argument or in pilot_manifest.json")

    dry_run_result = run_manual_pilot(
        tender_root=str(resolved_tender_root),
        tender_id=resolved_tender_id,
        instructions_text=_load_optional_text(instructions_text_file),
        pricing_file=resolved_pricing_file,
        workspace_root=str(workspace_root_path),
        workspace_pilot_id=pilot_id,
    )

    approval_gate = manual_approval_service.evaluate_manual_approval_gate(dry_run_result)
    approval_record = manual_approval_service.build_manual_approval_record(
        dry_run_result,
        tender_id=resolved_tender_id,
        tender_root=str(resolved_tender_root),
        pricing_file=resolved_pricing_file,
        operator_name=operator_name,
        confirm_approval=confirm_approval,
    )
    approval_outcome: Dict[str, Any] = {
        "status": "recorded" if approval_gate["approved"] and confirm_approval else "refused",
        "reason": "" if approval_gate["approved"] and confirm_approval else ("confirmation_missing" if not confirm_approval else "approval_gate_failed"),
        "gate": approval_gate,
        "approval_record": approval_record,
    }
    if approval_outcome["status"] == "recorded":
        manual_approval_service.append_manual_approval(approval_record)
        _update_pilot_status(
            pilot_dir,
            {
                "status": "approved",
                "submission_ready": True,
                "latest_run": {
                    "status": "approved",
                    "quote_pack_quality_status": _clean(dry_run_result.get("quote_pack_quality_status")),
                    "approval_blocked": bool(dry_run_result.get("approval_blocked", False)),
                    "submission_ready": True,
                    "blocker": "",
                },
            },
        )

    proof_record: Optional[Dict[str, Any]] = None
    review_record: Optional[Dict[str, Any]] = None
    proof_requested = bool(record_proof)
    if record_proof and approval_outcome["status"] == "recorded":
        if not portal_name or not submission_reference:
            raise ValueError("portal_name and submission_reference are required when --record-proof is supplied")
        review_record = review_submission_pack.review_submission_pack(
            tender_id=resolved_tender_id,
            tender_root=str(resolved_tender_root),
        )
        if review_record.get("submission_review_ready", False):
            proof_record = record_manual_submission_proof.record_manual_submission_proof(
                tender_id=resolved_tender_id,
                tender_root=str(resolved_tender_root),
                portal_name=portal_name,
                submission_reference=submission_reference,
                submitted_by=operator_name,
                proof_file=proof_file or "",
            )
            if proof_record.get("status") == "recorded":
                _update_pilot_status(
                    pilot_dir,
                    {
                        "status": "submitted",
                        "manual_submission_recorded": True,
                        "latest_submission_proof": proof_record,
                    },
                )
                record_pilot_run(
                    {
                        "tender_id": resolved_tender_id,
                        "tender_root": str(resolved_tender_root),
                        "workflow_stage": "proof_recorded",
                        "pilot_mode": "supervised_live",
                        "operator": operator_name,
                        "actor": operator_name,
                        "outcome": "completed",
                        "status": "recorded",
                        "warnings": [],
                        "failures": [],
                        "recovery_events": [],
                        "proof_confirmed": True,
                        "approval_confirmed": True,
                        "manual_submission_confirmed": True,
                        "final_submission_attempted": False,
                    }
                )

    if approval_outcome["status"] != "recorded":
        next_step = "record manual approval first"
    elif not record_proof:
        next_step = "record proof after the live manual submission"
    elif review_record and review_record.get("submission_review_ready", False) is False:
        next_step = "fix review blockers"
    elif proof_record and proof_record.get("status") == "recorded":
        next_step = "pilot flow complete"
    else:
        next_step = "fix proof capture blockers"
    summary = _build_summary(
        pilot_id=pilot_id,
        tender_id=resolved_tender_id,
        dry_run_result=dry_run_result,
        approval_outcome=approval_outcome,
        proof_record=proof_record,
        proof_requested=proof_requested,
        next_step=next_step,
    )
    summary["dry_run_result"] = dry_run_result
    summary["approval_outcome"] = approval_outcome
    summary["review_record"] = review_record
    summary["proof_record"] = proof_record
    summary["operator_name"] = operator_name
    summary["pricing_file"] = resolved_pricing_file
    summary["tender_root"] = str(resolved_tender_root)
    return summary


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the narrow supervised pilot week flow for one workspace pilot.")
    parser.add_argument("--workspace-root", required=True, help="Pilot workspace root containing PILOT-001 etc.")
    parser.add_argument("--pilot-id", required=True, help="Pilot folder name such as PILOT-001.")
    parser.add_argument("--confirm-approval", action="store_true", help="Required confirmation gate for manual approval.")
    parser.add_argument(
        "--operator-name",
        default="",
        help="Operator name to record in approval/proof logs. Defaults to LMCP_OPERATOR_NAME or Supervisor.",
    )
    parser.add_argument("--tender-root", default=None, help="Optional explicit RFQ/tender root for the supervised pilot.")
    parser.add_argument("--tender-id", default=None, help="Optional explicit tender identifier for the supervised pilot.")
    parser.add_argument("--pricing-file", default=None, help="Optional pricing JSON file to pass to the dry-run pipeline.")
    parser.add_argument("--instructions-text-file", default=None, help="Optional text file to use as tender instructions.")
    parser.add_argument("--record-proof", action="store_true", help="Record manual submission proof after the operator submits.")
    parser.add_argument("--portal-name", default=None, help="Portal or channel name used for the manual submission.")
    parser.add_argument("--submission-reference", default=None, help="Reference returned by the portal or manual process.")
    parser.add_argument("--proof-file", default=None, help="Optional proof file path to attach when recording proof.")
    args = parser.parse_args(argv)

    operator_name = _clean(args.operator_name) or _clean(os.getenv("LMCP_OPERATOR_NAME")) or "Supervisor"
    summary = run_supervised_pilot_week(
        workspace_root=args.workspace_root,
        pilot_id=args.pilot_id,
        confirm_approval=bool(args.confirm_approval),
        operator_name=operator_name,
        tender_root=args.tender_root,
        tender_id=args.tender_id,
        pricing_file=args.pricing_file,
        instructions_text_file=args.instructions_text_file,
        portal_name=args.portal_name,
        submission_reference=args.submission_reference,
        proof_file=args.proof_file,
        record_proof=bool(args.record_proof),
    )
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))

    if not summary["approval_outcome"]["approval_record"].get("manual_approval_recorded", False):
        print("supervised pilot halted: manual approval was not recorded")
        return 1
    if bool(args.record_proof) and not bool(summary.get("proof_record") and summary["proof_record"].get("manual_submission_recorded", False)):
        print("supervised pilot halted: proof capture did not complete")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
