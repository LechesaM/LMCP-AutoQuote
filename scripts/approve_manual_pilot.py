from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services import manual_approval_service
from scripts.run_manual_pilot import run_manual_pilot


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _warnings(result: Dict[str, Any]) -> List[str]:
    warnings = result.get("warnings")
    if isinstance(warnings, list):
        return [_clean(item) for item in warnings if _clean(item)]
    if warnings:
        return [_clean(warnings)]
    return []


def _print_result(result: Dict[str, Any], approval_record: Dict[str, Any]) -> None:
    print(f"status: {_clean(result.get('status'))}")
    print(f"quote pack quality status: {_clean(result.get('quote_pack_quality_status'))}")
    print(f"approval blocked: {str(bool(result.get('approval_blocked', False))).lower()}")
    print(f"pricing items unmatched: {int(result.get('pricing_items_unmatched', 0) or 0)}")
    print(f"warnings: {'; '.join(_warnings(result)) or 'none'}")
    print(f"manual approval recorded: {str(bool(approval_record.get('manual_approval_recorded', False))).lower()}")
    print(f"approved by operator: {str(bool(approval_record.get('approved_by_operator', False))).lower()}")
    print(f"submission ready: {str(bool(approval_record.get('submission_ready', False))).lower()}")
    print(f"final submission attempted: {str(bool(approval_record.get('final_submission_attempted', False))).lower()}")
    print(f"approval log location: {manual_approval_service.APPROVAL_LOG_FILE}")


def approve_manual_pilot(
    *,
    tender_root: str,
    tender_id: str,
    pricing_file: str,
    confirm_approval: bool,
    operator_name: str = "",
    instructions_text: Optional[str] = None,
    workspace_root: Optional[str] = None,
    workspace_pilot_id: Optional[str] = None,
) -> Dict[str, Any]:
    result = run_manual_pilot(
        tender_root=tender_root,
        tender_id=tender_id,
        instructions_text=instructions_text,
        pricing_file=pricing_file,
        workspace_root=workspace_root,
        workspace_pilot_id=workspace_pilot_id,
    )
    gate = manual_approval_service.evaluate_manual_approval_gate(result)
    if not confirm_approval:
        return {
            "status": "refused",
            "result": result,
            "approval_record": manual_approval_service.build_manual_approval_record(
                result,
                tender_id=tender_id,
                tender_root=tender_root,
                pricing_file=pricing_file,
                operator_name=operator_name,
                confirm_approval=False,
            ),
            "gate": gate,
            "reason": "confirmation_missing",
        }

    if not gate["approved"]:
        return {
            "status": "refused",
            "result": result,
            "approval_record": manual_approval_service.build_manual_approval_record(
                result,
                tender_id=tender_id,
                tender_root=tender_root,
                pricing_file=pricing_file,
                operator_name=operator_name,
                confirm_approval=True,
            ),
            "gate": gate,
            "reason": "approval_gate_failed",
        }

    approval_record = manual_approval_service.build_manual_approval_record(
        result,
        tender_id=tender_id,
        tender_root=tender_root,
        pricing_file=pricing_file,
        operator_name=operator_name,
        confirm_approval=True,
    )
    manual_approval_service.append_manual_approval(approval_record)
    return {
        "status": "recorded",
        "result": result,
        "approval_record": approval_record,
        "gate": gate,
        "reason": "",
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Safely record manual approval for an approval-ready pilot pack.")
    parser.add_argument("--tender-id", required=True, help="Stable tender identifier for the pilot run.")
    parser.add_argument("--tender-root", required=True, help="Folder containing the RFQ/tender pack.")
    parser.add_argument("--pricing-file", required=True, help="Manual pricing JSON used for the approval-ready pack.")
    parser.add_argument("--confirm-approval", action="store_true", help="Required confirmation gate.")
    parser.add_argument(
        "--operator-name",
        default="",
        help="Operator name to record in the approval log. Defaults to LMCP_OPERATOR_NAME or Supervisor.",
    )
    parser.add_argument("--pilot-workspace-root", default=None, help="Optional pilot workspace root for live run logs.")
    parser.add_argument("--pilot-workspace-id", default=None, help="Optional pilot workspace folder name such as PILOT-001.")
    args = parser.parse_args(argv)

    operator_name = args.operator_name.strip() or os.getenv("LMCP_OPERATOR_NAME", "").strip() or "Supervisor"
    outcome = approve_manual_pilot(
        tender_root=args.tender_root,
        tender_id=args.tender_id,
        pricing_file=args.pricing_file,
        confirm_approval=args.confirm_approval,
        operator_name=operator_name,
        workspace_root=args.pilot_workspace_root,
        workspace_pilot_id=args.pilot_workspace_id,
    )
    _print_result(outcome["result"], outcome["approval_record"])

    if outcome["status"] != "recorded":
        gate = outcome.get("gate") or {}
        blockers = gate.get("blockers") or []
        if outcome.get("reason") == "confirmation_missing":
            print("approval refused: --confirm-approval is required")
        elif blockers:
            print(f"approval refused: {'; '.join(blockers)}")
        else:
            print("approval refused")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
