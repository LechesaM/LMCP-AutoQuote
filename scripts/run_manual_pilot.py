from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services import pilot_run_log_service
from app.services.tender_submission_pipeline import TenderSubmissionPipeline


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _mandatory_forms(result: Dict[str, Any]) -> List[str]:
    form_plan = result.get("form_plan") if isinstance(result.get("form_plan"), dict) else {}
    forms: List[str] = []
    for item in _safe_list(form_plan.get("required_forms")):
        if not isinstance(item, dict):
            continue
        form_code = _clean(item.get("form_code"))
        if form_code:
            forms.append(form_code)
    return forms


def _warnings(result: Dict[str, Any]) -> List[str]:
    warnings = [_clean(item) for item in _safe_list(result.get("warnings")) if _clean(item)]
    if warnings:
        return warnings
    classification = result.get("classification") if isinstance(result.get("classification"), dict) else {}
    if _clean(result.get("status")) == "blocked":
        return [_clean(item) for item in _safe_list(classification.get("reasons")) if _clean(item)]
    return []


def _errors(result: Dict[str, Any]) -> List[str]:
    if _clean(result.get("status")) == "blocked" and _clean(result.get("message")):
        return [_clean(result.get("message"))]
    return []


def _quote_pack_generated(result: Dict[str, Any]) -> bool:
    if result.get("quote_pack_generated") is not None:
        return bool(result.get("quote_pack_generated"))
    final_files = [_clean(item) for item in _safe_list(result.get("final_files")) if _clean(item)]
    return any(path.endswith(".pdf") for path in final_files)


def _submission_pack_generated(result: Dict[str, Any]) -> bool:
    if result.get("submission_pack_generated") is not None:
        return bool(result.get("submission_pack_generated"))
    submission_pack = result.get("submission_pack") if isinstance(result.get("submission_pack"), dict) else {}
    return bool(submission_pack.get("submission_pack_ready_count", 0))


def _quote_pack_quality_status(result: Dict[str, Any]) -> str:
    return _clean(result.get("quote_pack_quality_status") or "unknown")


def _approval_blocked(result: Dict[str, Any]) -> bool:
    return bool(result.get("approval_blocked", False))


def _extracted_line_item_descriptions(result: Dict[str, Any]) -> List[str]:
    return [_clean(item) for item in _safe_list(result.get("extracted_line_item_descriptions")) if _clean(item)]


def _workspace_section_for_stage(stage_key: str) -> str:
    if stage_key in {"tender_pack_intake", "archive_extraction", "rfq_document_analysis"}:
        return "Import"
    if stage_key in {
        "mandatory_form_detection",
        "company_director_data_injection",
        "quote_submission_pack_generation",
        "proof_audit_output",
        "quote_pack_quality_assessment",
        "human_approval_gate",
    }:
        return "Review"
    return "Outcome"


def _append_workspace_run_log(result: Dict[str, Any], workspace_root: str, pilot_id: str) -> Optional[str]:
    log_path: Optional[str] = None
    stages = [stage for stage in _safe_list(result.get("pipeline_stages")) if isinstance(stage, dict)]
    for stage in stages:
        stage_key = _clean(stage.get("key") or stage.get("stage") or stage.get("name") or "stage")
        section = _workspace_section_for_stage(stage_key)
        details = stage.get("details") if isinstance(stage.get("details"), dict) else {}
        fields = {
            "Stage": stage.get("name") or stage_key,
            "Stage Key": stage_key,
            "Status": stage.get("status", ""),
        }
        for key in (
            "tender_root",
            "file_count",
            "supported_file_count",
            "required_form_count",
            "missing_form_count",
            "document_count",
            "quote_pack_quality_status",
            "approval_blocked",
            "submission_pack_manifest_path",
            "audit_output_path",
            "message",
            "reason",
        ):
            if key in details:
                fields[key] = details.get(key)
        log_path = pilot_run_log_service.append_workspace_log_entry(
            workspace_root,
            pilot_id,
            section,
            fields=fields,
        )

    pilot_run_log_service.append_workspace_log_entry(
        workspace_root,
        pilot_id,
        "Outcome",
        fields={
            "Status": result.get("status"),
            "Quote Pack Quality Status": result.get("quote_pack_quality_status"),
            "Approval Blocked": bool(result.get("approval_blocked", False)),
            "Submission Ready": bool(result.get("submission_ready", False)),
            "Quote Pack Generated": _quote_pack_generated(result),
            "Submission Pack Generated": _submission_pack_generated(result),
            "Pricing Items Matched": int(result.get("pricing_items_matched", 0) or 0),
            "Pricing Items Unmatched": int(result.get("pricing_items_unmatched", 0) or 0),
        },
        notes=[
            f"Warnings: {'; '.join(_warnings(result)) or 'none'}",
            f"Errors: {'; '.join(_errors(result)) or 'none'}",
        ],
    )
    return log_path


def run_manual_pilot(
    *,
    tender_root: str,
    tender_id: str,
    instructions_text: Optional[str] = None,
    pricing_file: Optional[str] = None,
    workspace_root: Optional[str] = None,
    workspace_pilot_id: Optional[str] = None,
) -> Dict[str, Any]:
    pipeline = TenderSubmissionPipeline()
    result = pipeline.run(
        tender_root=tender_root,
        tender_id=tender_id,
        instructions_text=instructions_text,
        pricing_file=pricing_file,
        mode="assisted_production",
        dry_run=True,
        require_human_approval=True,
        human_approval_granted=False,
    )
    if workspace_root and workspace_pilot_id:
        _append_workspace_run_log(result, workspace_root, workspace_pilot_id)
    return result


def print_summary(result: Dict[str, Any]) -> None:
    classification = result.get("classification") if isinstance(result.get("classification"), dict) else {}
    print(f"status: {_clean(result.get('status'))}")
    print(f"detected category: {_clean(classification.get('decision') or 'unknown')}")
    print(f"excluded: {str(not bool(classification.get('eligible', False))).lower()}")
    print(f"mandatory forms detected: {', '.join(_mandatory_forms(result)) or 'none'}")
    print(f"quote pack generated: {str(_quote_pack_generated(result)).lower()}")
    print(f"submission pack generated: {str(_submission_pack_generated(result)).lower()}")
    print(f"quote pack quality status: {_quote_pack_quality_status(result)}")
    print(f"approval blocked: {str(_approval_blocked(result)).lower()}")
    print(f"extracted line item count: {int(result.get('extracted_line_item_count', 0) or 0)}")
    print(f"extracted line item descriptions: {', '.join(_extracted_line_item_descriptions(result)) or 'none'}")
    print(f"pricing file loaded: {str(bool(result.get('pricing_file_loaded', False))).lower()}")
    print(f"pricing file item count: {int(result.get('pricing_file_item_count', 0) or 0)}")
    print(f"pricing items matched: {int(result.get('pricing_items_matched', 0) or 0)}")
    print(f"pricing items unmatched: {int(result.get('pricing_items_unmatched', 0) or 0)}")
    print(f"warnings: {'; '.join(_warnings(result)) or 'none'}")
    print(f"errors: {'; '.join(_errors(result)) or 'none'}")
    print("final submission attempted: false")
    print(f"pilot log location: {pilot_run_log_service.PILOT_RUN_LOG_FILE}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run a real RFQ assisted-production manual pilot dry-run.")
    parser.add_argument("--tender-root", required=True, help="Folder containing the RFQ/tender pack.")
    parser.add_argument("--tender-id", required=True, help="Stable tender identifier for the pilot run.")
    parser.add_argument("--instructions-text", default=None, help="Optional extracted instructions or tender text.")
    parser.add_argument("--pricing-file", default=None, help="Optional JSON file with manual supplier pricing input.")
    parser.add_argument("--pilot-workspace-root", default=None, help="Optional pilot workspace root for appending live run logs.")
    parser.add_argument("--pilot-workspace-id", default=None, help="Optional pilot workspace folder name such as PILOT-001.")
    args = parser.parse_args(argv)

    result = run_manual_pilot(
        tender_root=args.tender_root,
        tender_id=args.tender_id,
        instructions_text=args.instructions_text,
        pricing_file=args.pricing_file,
        workspace_root=args.pilot_workspace_root,
        workspace_pilot_id=args.pilot_workspace_id,
    )
    print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
