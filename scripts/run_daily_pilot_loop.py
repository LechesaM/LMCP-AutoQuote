from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.pilot import get_pilot_summary
from scripts.check_controlled_operation_readiness import build_controlled_operation_readiness_report
from scripts.run_supervised_pilot_week import run_supervised_pilot_week


RUNTIME_ROOT = PROJECT_ROOT / "runtime"
MANUAL_PRODUCTION_ROOT = RUNTIME_ROOT / "manual_production"
LIVE_QUEUE_PATH = RUNTIME_ROOT / "live_rfqs.json"
SOURCE_BUNDLE_ROOT = MANUAL_PRODUCTION_ROOT / "source_bundle_repairs"
SUBMISSION_PACKAGE_ROOT = MANUAL_PRODUCTION_ROOT / "submission_packages"
DEFAULT_REPORT_PATH = MANUAL_PRODUCTION_ROOT / "daily_pilot_loop_report.json"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _slugify(value: str) -> str:
    text = _clean(value)
    if not text:
        return ""
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    return text.strip("._")


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return payload


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not path.exists():
        return items
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _daily_loop_cursor_path() -> Path:
    return MANUAL_PRODUCTION_ROOT / "daily_pilot_loop_cursor.json"


def _read_cursor(path: Optional[Path] = None) -> Dict[str, Any]:
    path = path or _daily_loop_cursor_path()
    payload = _read_json(path)
    return payload if isinstance(payload, dict) else {}


def _write_cursor(path: Optional[Path], tender_id: str, candidate_mode: str) -> None:
    path = path or _daily_loop_cursor_path()
    existing = _read_cursor(path)
    recent: List[str] = []
    if isinstance(existing.get("recent_selected_tender_ids"), list):
        recent.extend(_clean(value) for value in existing.get("recent_selected_tender_ids", []) if _clean(value))
    elif _clean(existing.get("last_selected_tender_id")):
        recent.append(_clean(existing.get("last_selected_tender_id")))
    recent.append(_clean(tender_id))
    deduped: List[str] = []
    for value in recent:
        if value and value not in deduped:
            deduped.append(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "last_selected_tender_id": _clean(tender_id),
                "recent_selected_tender_ids": deduped,
                "last_selected_mode": _clean(candidate_mode),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _completed_tenders() -> set[str]:
    completed: set[str] = set()
    for record in _read_jsonl(MANUAL_PRODUCTION_ROOT / "pilot_runs.jsonl"):
        if _clean(record.get("outcome")).lower() == "completed" or _clean(record.get("status")).lower() == "recorded":
            tender_id = _clean(record.get("tender_id"))
            if tender_id:
                completed.add(tender_id)
    return completed


def _candidate_id(item: Dict[str, Any]) -> str:
    for key in ("rfq_id", "reference", "external_id", "rfq_number", "document_number", "quote_number", "buyer_rfq_number", "title"):
        value = _clean(item.get(key))
        if value:
            return value
    return ""


def _candidate_priority(item: Dict[str, Any]) -> int:
    status = _clean(item.get("status")).lower()
    pipeline_status = _clean(item.get("pipeline_status")).lower()
    quote_ready = bool(item.get("quote_ready", False))
    if quote_ready or status == "quote ready" or pipeline_status == "quote_ready_validated":
        return 0
    if status == "review required" or pipeline_status == "quantity_verification_required":
        return 1
    if status == "manual pricing required" or pipeline_status == "manual_pricing_required":
        return 2
    return 3


def _candidate_recency_score(item: Dict[str, Any]) -> float:
    for key in ("created_at", "updated_at"):
        raw = _clean(item.get(key))
        if not raw:
            continue
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
    return 0.0


def _queue_selection_summary(queue: Dict[str, Any], completed: Optional[set[str]] = None) -> Dict[str, Any]:
    completed = completed or _completed_tenders()
    items = [item for item in queue.get("items", []) if isinstance(item, dict)]
    fresh_runnable = 0
    repeat_runnable = 0
    unavailable = 0
    for item in items:
        tender_id = _candidate_id(item)
        bundle_root = next((path for path in _bundle_roots(tender_id) if path.exists() and path.is_dir()), None) if tender_id else None
        pricing_file = next((path for path in _pricing_files(tender_id) if path.exists()), None) if tender_id else None
        runnable = bool(tender_id and bundle_root and pricing_file and _pricing_file_is_approval_ready(pricing_file))
        if not runnable:
            unavailable += 1
            continue
        if tender_id in completed:
            repeat_runnable += 1
        else:
            fresh_runnable += 1
    return {
        "queue_items": len(items),
        "fresh_runnable_candidates": fresh_runnable,
        "repeat_runnable_candidates": repeat_runnable,
        "unavailable_candidates": unavailable,
        "completed_tenders": len(completed),
    }


def _bundle_roots(tender_id: str) -> Iterable[Path]:
    slug = _slugify(tender_id)
    names = [tender_id]
    if slug and slug not in names:
        names.append(slug)
    for base in (SOURCE_BUNDLE_ROOT, MANUAL_PRODUCTION_ROOT / "review_ready_bundles", MANUAL_PRODUCTION_ROOT / "e2e_rfqs"):
        for name in names:
            yield base / name


def _pricing_files(tender_id: str) -> Iterable[Path]:
    slug = _slugify(tender_id)
    names = [tender_id]
    if slug and slug not in names:
        names.append(slug)
    suffixes = (
        "__manual_pricing.json",
        "__manual_pricing_restored_from_governed_quote_pack.json",
    )
    for name in names:
        package_dir = SUBMISSION_PACKAGE_ROOT / name
        for suffix in suffixes:
            candidate = package_dir / f"{name}{suffix}"
            if candidate.exists():
                yield candidate
        if package_dir.exists():
            for candidate in sorted(package_dir.glob("*manual_pricing*.json")):
                if candidate.exists():
                    yield candidate


def _pricing_file_is_approval_ready(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return False
    for item in items:
        if not isinstance(item, dict):
            return False
        unit_price = float(item.get("unit_price") or 0.0)
        line_total = float(item.get("line_total") or 0.0)
        if unit_price <= 0 or line_total <= 0:
            return False
    return True


class DailyCandidate:
    def __init__(
        self,
        *,
        tender_id: str,
        source_name: str,
        title: str,
        status: str,
        pipeline_status: str,
        eligible: bool,
        bundle_root: Path,
        pricing_file: Path,
        repeat_run: bool,
    ) -> None:
        self.tender_id = tender_id
        self.source_name = source_name
        self.title = title
        self.status = status
        self.pipeline_status = pipeline_status
        self.eligible = eligible
        self.bundle_root = bundle_root
        self.pricing_file = pricing_file
        self.repeat_run = repeat_run


def _select_candidate(
    queue: Dict[str, Any],
    *,
    allow_repeat: bool = True,
    allow_bundle_fallback: bool = True,
    skip_tender_ids: Optional[set[str]] = None,
) -> Optional[DailyCandidate]:
    completed = _completed_tenders()
    skip_tender_ids = {_clean(tender_id) for tender_id in (skip_tender_ids or set()) if _clean(tender_id)}
    items = [item for item in queue.get("items", []) if isinstance(item, dict)]
    items.sort(key=lambda item: (_candidate_priority(item), -_candidate_recency_score(item)))

    def _build_candidate(item: Dict[str, Any], repeat_run: bool) -> Optional[DailyCandidate]:
        tender_id = _candidate_id(item)
        if not tender_id:
            return None
        if tender_id in skip_tender_ids:
            return None
        bundle_root = next((path for path in _bundle_roots(tender_id) if path.exists() and path.is_dir()), None)
        if not bundle_root:
            return None
        pricing_file = next((path for path in _pricing_files(tender_id) if path.exists()), None)
        if not pricing_file:
            return None
        if not _pricing_file_is_approval_ready(pricing_file):
            return None
        return DailyCandidate(
            tender_id=tender_id,
            source_name=_clean(item.get("source_name") or item.get("buyer_name") or "live queue"),
            title=_clean(item.get("title") or item.get("buyer_rfq_number") or tender_id),
            status=_clean(item.get("status")),
            pipeline_status=_clean(item.get("pipeline_status")),
            eligible=bool(item.get("eligible", False)),
            bundle_root=bundle_root,
            pricing_file=pricing_file,
            repeat_run=repeat_run,
        )

    fresh_candidates: List[DailyCandidate] = []
    repeat_candidates: List[DailyCandidate] = []
    for item in items:
        tender_id = _candidate_id(item)
        if not tender_id:
            continue
        repeat_run = tender_id in completed
        candidate = _build_candidate(item, repeat_run)
        if not candidate:
            continue
        if repeat_run:
            repeat_candidates.append(candidate)
        else:
            fresh_candidates.append(candidate)

    if fresh_candidates:
        return fresh_candidates[0]
    if allow_repeat and repeat_candidates:
        return repeat_candidates[0]

    if allow_bundle_fallback:
        # Fall back to any bundle on disk so the command can still be used
        # interactively even when the live queue is empty.
        for base in (SOURCE_BUNDLE_ROOT, MANUAL_PRODUCTION_ROOT / "review_ready_bundles", MANUAL_PRODUCTION_ROOT / "e2e_rfqs"):
            if not base.exists():
                continue
            for bundle_root in sorted(path for path in base.iterdir() if path.is_dir()):
                tender_id = bundle_root.name
                pricing_file = next((path for path in _pricing_files(tender_id) if path.exists()), None)
                if not pricing_file:
                    continue
                if not _pricing_file_is_approval_ready(pricing_file):
                    continue
                repeat_run = tender_id in completed
                if tender_id in skip_tender_ids:
                    continue
                return DailyCandidate(
                    tender_id=tender_id,
                    source_name="bundle fallback",
                    title=tender_id,
                    status="unknown",
                    pipeline_status="unknown",
                    eligible=True,
                    bundle_root=bundle_root,
                    pricing_file=pricing_file,
                    repeat_run=repeat_run,
                )

    return None


def _ensure_workspace(pilot_id: str, candidate: DailyCandidate, workspace_root: Path) -> Path:
    pilot_dir = workspace_root / pilot_id
    pilot_dir.mkdir(parents=True, exist_ok=True)
    (pilot_dir / "submission_logs").mkdir(parents=True, exist_ok=True)

    rfq_source = pilot_dir / "rfq_source"
    if not rfq_source.exists():
        try:
            rfq_source.symlink_to(candidate.bundle_root, target_is_directory=True)
        except Exception:
            if candidate.bundle_root.is_dir():
                shutil.copytree(candidate.bundle_root, rfq_source)
            else:
                raise

    pilot_status = {
        "rfq_number": candidate.tender_id,
        "tender_id": candidate.tender_id,
        "status": "queued",
        "source_name": candidate.source_name,
        "title": candidate.title,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (pilot_dir / "submission_logs" / "pilot_status.json").write_text(json.dumps(pilot_status, indent=2), encoding="utf-8")

    pilot_manifest = {
        "pricing_file": str(candidate.pricing_file),
        "pilot_scope": ["daily supervised loop", "approval", "review", "proof"],
        "success_criteria": ["dry-run succeeds", "approval records", "review records", "proof records"],
        "candidate": {
            "tender_id": candidate.tender_id,
            "repeat_run": candidate.repeat_run,
            "source_name": candidate.source_name,
        },
    }
    (pilot_dir / "pilot_manifest.json").write_text(json.dumps(pilot_manifest, indent=2), encoding="utf-8")
    return pilot_dir


def _build_report(candidate: DailyCandidate, result: Dict[str, Any], readiness: Dict[str, Any], pilot_id: str, workspace_root: Path) -> Dict[str, Any]:
    thresholds = readiness.get("thresholds") if isinstance(readiness.get("thresholds"), dict) else {}
    summary = readiness.get("pilot_summary") if isinstance(readiness.get("pilot_summary"), dict) else {}
    operator_actions_next = _operator_actions_next(result, readiness)
    return {
        "pilot_id": pilot_id,
        "workspace_root": str(workspace_root),
        "tender_id": candidate.tender_id,
        "title": candidate.title,
        "status": _clean(result.get("dry_run_status")),
        "quote_pack_quality_status": _clean(result.get("quote_pack_quality_status")),
        "approval_status": _clean(result.get("approval_status")),
        "proof_status": _clean(result.get("proof_status")),
        "next_step": _clean(result.get("next_step")),
        "manual_approval_recorded": bool(result.get("manual_approval_recorded", False)),
        "manual_submission_recorded": bool(result.get("manual_submission_recorded", False)),
        "repeat_run": candidate.repeat_run,
        "controlled_operation_ready": bool(readiness.get("controlled_operation_ready", False)),
        "readiness_score": float(thresholds.get("readiness_score", 0) or 0),
        "successful_pilot_runs": int(summary.get("successful_runs", 0) or 0),
        "total_pilot_runs": int(summary.get("total_runs", 0) or 0),
        "failed_pilot_runs": int(summary.get("failed_runs", 0) or 0),
        "operator_actions_next": operator_actions_next,
    }


def _operator_actions_next(result: Dict[str, Any], readiness: Dict[str, Any]) -> List[str]:
    actions: List[str] = []
    report_ready = bool(readiness.get("controlled_operation_ready", False))
    next_step = _clean(result.get("next_step"))
    if next_step == "pilot flow complete":
        actions.extend(
            [
                "Confirm the proof and approval entries are retained in runtime/manual_production",
                "Review the JSON report before starting the next RFQ",
                "Check the live RFQ queue for the next runnable candidate",
            ]
        )
    elif next_step == "record manual approval first":
        actions.extend(
            [
                "Review the dry-run output with the operator",
                "Record manual approval before proceeding",
            ]
        )
    elif next_step == "record proof after the live manual submission":
        actions.extend(
            [
                "Complete the manual buyer submission",
                "Record proof immediately after the submission is sent",
            ]
        )
    elif next_step == "fix review blockers":
        actions.extend(
            [
                "Inspect the submission review blockers",
                "Repair missing artifacts before recording proof",
            ]
        )
    elif next_step == "fix proof capture blockers":
        actions.extend(
            [
                "Check the review record and proof-file path",
                "Capture proof once the review-ready record exists",
            ]
        )
    else:
        actions.append("Inspect the daily report and decide whether to continue the loop")
    if report_ready and not actions:
        actions.append("Proceed to the next queued RFQ")
    if not report_ready:
        actions.append("Resolve controlled-operation blockers before expanding scope")
    return actions


def run_daily_pilot_loop(
    *,
    workspace_root: str,
    operator_name: str,
    allow_repeat: bool = True,
    allow_bundle_fallback: bool = True,
    record_proof: bool = True,
    queue_file: Optional[str] = None,
    report_file: Optional[str] = None,
    portal_name: Optional[str] = None,
    submission_reference: Optional[str] = None,
    proof_file: Optional[str] = None,
    rfq_id: Optional[str] = None,
) -> Dict[str, Any]:
    queue_path = Path(queue_file).expanduser().resolve() if queue_file else LIVE_QUEUE_PATH
    queue = _read_json(queue_path)
    completed = _completed_tenders()
    selection_summary = _queue_selection_summary(queue, completed=completed)
    cursor_path = _daily_loop_cursor_path()
    cursor = _read_cursor(cursor_path)
    cursor_tender_ids: set[str] = set()
    if isinstance(cursor.get("recent_selected_tender_ids"), list):
        cursor_tender_ids.update(_clean(value) for value in cursor.get("recent_selected_tender_ids", []) if _clean(value))
    elif _clean(cursor.get("last_selected_tender_id")):
        cursor_tender_ids.add(_clean(cursor.get("last_selected_tender_id")))
    if rfq_id:
        queue = dict(queue)
        items = [item for item in queue.get("items", []) if isinstance(item, dict)]
        queue["items"] = [item for item in items if _candidate_id(item) == _clean(rfq_id)]
        selection_summary = _queue_selection_summary(queue, completed=completed)
    workspace_root_path = Path(workspace_root).expanduser().resolve()
    excluded_tender_ids: set[str] = set()
    last_candidate: Optional[DailyCandidate] = None
    last_result: Dict[str, Any] = {}
    last_pilot_id = ""
    last_submission_reference = ""

    while True:
        working_queue = dict(queue)
        working_items = [item for item in working_queue.get("items", []) if isinstance(item, dict)]
        if excluded_tender_ids:
            working_items = [item for item in working_items if _candidate_id(item) not in excluded_tender_ids]
        working_queue["items"] = working_items
        current_selection_summary = _queue_selection_summary(working_queue, completed=completed)
        skip_tender_ids = set(excluded_tender_ids)
        skip_tender_ids.update(cursor_tender_ids)
        candidate = _select_candidate(
            working_queue,
            allow_repeat=allow_repeat,
            allow_bundle_fallback=allow_bundle_fallback,
            skip_tender_ids=skip_tender_ids,
        )
        if not candidate and current_selection_summary.get("fresh_runnable_candidates", 0) > 0 and cursor_tender_ids:
            candidate = _select_candidate(
                working_queue,
                allow_repeat=allow_repeat,
                allow_bundle_fallback=allow_bundle_fallback,
                skip_tender_ids=excluded_tender_ids,
            )
        if not candidate:
            readiness = build_controlled_operation_readiness_report(limit=20)
            if not last_candidate:
                no_candidate_result: Dict[str, Any] = {}
                no_candidate_report = {
                    "status": "no_candidate",
                    "message": "No runnable RFQ candidate was found in the live queue or local bundles.",
                    "controlled_operation_ready": bool(readiness.get("controlled_operation_ready", False)),
                    "selection_summary": current_selection_summary,
                }
                no_candidate_report["operator_actions_next"] = _operator_actions_next(no_candidate_result, readiness)
                payload = {
                    "selected": None,
                    "result": no_candidate_result,
                    "readiness": readiness,
                    "report": no_candidate_report,
                }
                _write_report(payload, report_file)
                return payload
            payload = {
                "selected": {
                    "tender_id": last_candidate.tender_id,
                    "title": last_candidate.title,
                    "source_name": last_candidate.source_name,
                    "status": last_candidate.status,
                    "pipeline_status": last_candidate.pipeline_status,
                    "eligible": last_candidate.eligible,
                    "bundle_root": str(last_candidate.bundle_root),
                    "pricing_file": str(last_candidate.pricing_file),
                    "repeat_run": last_candidate.repeat_run,
                    "pilot_id": last_pilot_id,
                    "submission_reference": last_submission_reference,
                },
                "result": last_result,
                "readiness": readiness,
                "report": {
                    **_build_report(last_candidate, last_result, readiness, last_pilot_id, workspace_root_path),
                    "selection_summary": current_selection_summary,
                    "candidate_mode": "repeat" if last_candidate.repeat_run else "fresh",
                },
            }
            _write_report(payload, report_file)
            return payload

        pilot_id = f"DAILY-{_slugify(candidate.tender_id) or 'RFQ'}"
        _ensure_workspace(pilot_id, candidate, workspace_root_path)

        generated_submission_reference = submission_reference or f"{candidate.tender_id}__submission__{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        result = run_supervised_pilot_week(
            workspace_root=str(workspace_root_path),
            pilot_id=pilot_id,
            confirm_approval=True,
            operator_name=operator_name,
            tender_root=str(candidate.bundle_root),
            tender_id=candidate.tender_id,
            pricing_file=str(candidate.pricing_file),
            record_proof=record_proof,
            portal_name=portal_name or candidate.source_name or candidate.title or "daily pilot",
            submission_reference=generated_submission_reference,
            proof_file=proof_file or "",
        )
        approval_recorded = bool(result.get("approval_status") == "recorded" and result.get("manual_approval_recorded", False))
        proof_recorded = (not record_proof) or bool(result.get("proof_status") == "recorded" and result.get("manual_submission_recorded", False))
        if approval_recorded and proof_recorded:
            readiness = build_controlled_operation_readiness_report(limit=20)
            _write_cursor(cursor_path, candidate.tender_id, "fresh" if not candidate.repeat_run else "repeat")
            payload = {
                "selected": {
                    "tender_id": candidate.tender_id,
                    "title": candidate.title,
                    "source_name": candidate.source_name,
                    "status": candidate.status,
                    "pipeline_status": candidate.pipeline_status,
                    "eligible": candidate.eligible,
                    "bundle_root": str(candidate.bundle_root),
                    "pricing_file": str(candidate.pricing_file),
                    "repeat_run": candidate.repeat_run,
                    "pilot_id": pilot_id,
                    "submission_reference": generated_submission_reference,
                },
                "result": result,
                "readiness": readiness,
                "report": {
                    **_build_report(candidate, result, readiness, pilot_id, workspace_root_path),
                    "selection_summary": current_selection_summary,
                    "candidate_mode": "repeat" if candidate.repeat_run else "fresh",
                },
            }
            _write_report(payload, report_file)
            return payload

        excluded_tender_ids.add(candidate.tender_id)
        last_candidate = candidate
        last_result = result
        last_pilot_id = pilot_id
        last_submission_reference = generated_submission_reference
        _write_cursor(cursor_path, candidate.tender_id, "fresh" if not candidate.repeat_run else "repeat")
        if len(excluded_tender_ids) >= len([item for item in queue.get("items", []) if isinstance(item, dict)]):
            readiness = build_controlled_operation_readiness_report(limit=20)
            payload = {
                "selected": {
                    "tender_id": candidate.tender_id,
                    "title": candidate.title,
                    "source_name": candidate.source_name,
                    "status": candidate.status,
                    "pipeline_status": candidate.pipeline_status,
                    "eligible": candidate.eligible,
                    "bundle_root": str(candidate.bundle_root),
                    "pricing_file": str(candidate.pricing_file),
                    "repeat_run": candidate.repeat_run,
                    "pilot_id": pilot_id,
                    "submission_reference": generated_submission_reference,
                },
                "result": result,
                "readiness": readiness,
                "report": {
                    **_build_report(candidate, result, readiness, pilot_id, workspace_root_path),
                    "selection_summary": current_selection_summary,
                    "candidate_mode": "repeat" if candidate.repeat_run else "fresh",
                },
            }
            _write_report(payload, report_file)
            return payload


def _write_report(payload: Dict[str, Any], report_file: Optional[str]) -> None:
    report_path = Path(report_file).expanduser().resolve() if report_file else DEFAULT_REPORT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _print_report(payload: Dict[str, Any]) -> None:
    report = payload.get("report") if isinstance(payload.get("report"), dict) else {}
    selected = payload.get("selected") if isinstance(payload.get("selected"), dict) else {}
    if report.get("status") == "no_candidate":
        print("daily pilot loop: no runnable candidate")
        print(report.get("message", "No runnable RFQ candidate was found."))
        print(f"controlled operation ready: {str(bool(report.get('controlled_operation_ready', False))).lower()}")
        return
    print(f"daily pilot loop: {selected.get('tender_id')} - {selected.get('title')}")
    print(f"source: {selected.get('source_name')}")
    print(f"repeat run: {str(bool(selected.get('repeat_run', False))).lower()}")
    print(f"status: {report.get('status')}")
    print(f"approval: {report.get('approval_status')}")
    print(f"proof: {report.get('proof_status')}")
    print(f"next step: {report.get('next_step')}")
    actions = report.get("operator_actions_next") or []
    if actions:
        print("next actions:")
        for action in actions:
            print(f"- {action}")
    print(f"controlled operation ready: {str(bool(report.get('controlled_operation_ready', False))).lower()}")
    print(f"readiness score: {report.get('readiness_score', 0)}")
    print(f"pilot runs: {report.get('successful_pilot_runs', 0)}/{report.get('total_pilot_runs', 0)} successful")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the daily supervised pilot loop against the best available RFQ candidate.")
    parser.add_argument("--workspace-root", default=str(MANUAL_PRODUCTION_ROOT), help="Workspace root where daily pilot folders should be created.")
    parser.add_argument("--operator-name", default=os.getenv("LMCP_OPERATOR_NAME", "Supervisor"), help="Operator name recorded in approvals and proofs.")
    parser.add_argument("--allow-repeat", action="store_true", default=True, help="Allow rerunning an already completed candidate if no fresh candidate is available.")
    parser.add_argument("--fresh-only", action="store_true", help="Do not rerun completed candidates.")
    parser.add_argument("--record-proof", action="store_true", default=True, help="Record proof as part of the daily loop.")
    parser.add_argument("--no-record-proof", action="store_true", help="Stop after the review-ready stage instead of recording proof.")
    parser.add_argument("--queue-file", default=str(LIVE_QUEUE_PATH), help="JSON live RFQ queue file to inspect.")
    parser.add_argument("--report-file", default=str(DEFAULT_REPORT_PATH), help="JSON report file to write after the run.")
    parser.add_argument("--portal-name", default=None, help="Portal or channel name used for proof capture.")
    parser.add_argument("--submission-reference", default=None, help="Submission reference for proof capture.")
    parser.add_argument("--proof-file", default=None, help="Optional proof file to attach when recording proof.")
    parser.add_argument("--rfq-id", default=None, help="Restrict the loop to a specific RFQ identifier.")
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON.")
    args = parser.parse_args(argv)

    payload = run_daily_pilot_loop(
        workspace_root=args.workspace_root,
        operator_name=args.operator_name,
        allow_repeat=not args.fresh_only,
        allow_bundle_fallback=not args.fresh_only,
        record_proof=False if args.no_record_proof else True,
        queue_file=args.queue_file,
        report_file=args.report_file,
        portal_name=args.portal_name,
        submission_reference=args.submission_reference,
        proof_file=args.proof_file,
        rfq_id=args.rfq_id,
    )

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        _print_report(payload)

    report = payload.get("report") if isinstance(payload.get("report"), dict) else {}
    if report.get("status") == "no_candidate":
        return 2
    return 0 if report.get("next_step") == "pilot flow complete" or report.get("status") == "recorded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
