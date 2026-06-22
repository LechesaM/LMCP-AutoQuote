from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.audit_trail_service import append_audit_event
from app.services.submission_pack_assembler_service import build_submission_pack as _build_submission_pack


def _clean(value: Any) -> str:
    return str(value or "").replace("\xa0", " ").strip()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _submission_package_workspace(tender_id: str) -> Path:
    from app.core.runtime_paths import get_runtime_paths

    return get_runtime_paths().manual_production_dir / "submission_packages" / tender_id


def _submission_pack_audit_log(runtime_dir: Optional[str] = None) -> Path:
    from app.core.runtime_paths import get_runtime_paths

    runtime_root = Path(runtime_dir).expanduser().resolve() if runtime_dir else get_runtime_paths().runtime_root
    return runtime_root / "manual_production" / "submission_pack_events.jsonl"


def _write_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not path.exists():
        return records
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(payload)
    except Exception:
        return []
    return records


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _find_value(data: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data.get(key) not in (None, ""):
            return data.get(key)
    for value in data.values():
        if isinstance(value, dict):
            found = _find_value(value, *keys)
            if found not in (None, ""):
                return found
    return None


def _collect_existing_files(value: Any) -> List[str]:
    collected: List[str] = []
    seen: set[str] = set()

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            for inner in item.values():
                walk(inner)
            return
        if isinstance(item, list):
            for inner in item:
                walk(inner)
            return
        text = _clean(item)
        if not text or text in seen:
            return
        if text.startswith("http://") or text.startswith("https://"):
            return
        try:
            path = Path(text).expanduser()
            if path.exists() and path.is_file():
                seen.add(text)
                collected.append(str(path))
        except Exception:
            return

    walk(value)
    return collected


def _pick_existing_path(detail: Dict[str, Any], keys: List[str], keywords: List[str], candidates: List[str]) -> str:
    explicit = _clean(_find_value(detail, *keys))
    if explicit:
        try:
            path = Path(explicit).expanduser()
            if path.exists() and path.is_file():
                return str(path)
        except Exception:
            pass

    for candidate in candidates:
        lower = candidate.lower()
        if all(keyword in lower for keyword in keywords):
            return candidate
    return ""


def _existing_unique(paths: List[str]) -> List[str]:
    output: List[str] = []
    seen: set[str] = set()
    for path in paths:
        cleaned = _clean(path)
        if not cleaned or cleaned in seen:
            continue
        try:
            p = Path(cleaned).expanduser()
            if not p.exists() or not p.is_file():
                continue
        except Exception:
            continue
        seen.add(cleaned)
        output.append(str(p))
    return output


def _workspace_candidate_paths(detail: Dict[str, Any]) -> List[str]:
    candidates: List[str] = []
    tender_id = _clean(detail.get("tender_id") or detail.get("rfq_number") or detail.get("buyer_rfq_number"))
    if tender_id:
        candidates.append(str(_submission_package_workspace(tender_id)))

    for path_value in (
        _find_value(_safe_dict(detail.get("submission_package")), "quote_pack_pdf_path", "quotePackPdfPath"),
        _find_value(_safe_dict(detail.get("submission_package")), "buyer_pricing_schedule_path", "buyerPricingSchedulePath"),
        _find_value(_safe_dict(detail.get("submission_package")), "submission_package_manifest_path", "submissionManifestPath", "submissionPackageManifestPath"),
        _find_value(_safe_dict(detail.get("submission_package")), "quote_pack_manifest_path", "quotePackManifestPath"),
    ):
        cleaned = _clean(path_value)
        if cleaned:
            candidates.append(str(Path(cleaned).expanduser().parent))

    workspace_files: List[str] = []
    seen: set[str] = set()
    for raw_path in candidates:
        try:
            workspace = Path(raw_path).expanduser()
        except Exception:
            continue
        if not workspace.exists() or not workspace.is_dir():
            continue
        for file_path in workspace.rglob("*"):
            if not file_path.is_file():
                continue
            resolved = str(file_path.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            workspace_files.append(resolved)
    return workspace_files


def _artifact_map(detail: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    submission_package = _safe_dict(detail.get("submission_package"))
    review_ready_bundle = _safe_dict(detail.get("review_ready_bundle"))
    governed_submission = _safe_dict(detail.get("governed_submission"))
    submission_execution = _safe_dict(detail.get("submission_execution"))

    candidate_paths = _existing_unique(
        _collect_existing_files(detail)
        + _collect_existing_files(submission_package)
        + _collect_existing_files(review_ready_bundle)
        + _collect_existing_files(governed_submission)
        + _collect_existing_files(submission_execution)
        + _workspace_candidate_paths(detail)
    )

    artifact_specs = {
        "buyer_pricing_schedule": {
            "keys": ["buyer_pricing_schedule_path", "buyerPricingSchedulePath"],
            "keywords": ["buyer", "pricing", "schedule"],
        },
        "formal_quotation": {
            "keys": ["quote_pack_pdf_path", "quotePackPdfPath", "final_pdf_path", "pdf_path"],
            "keywords": ["quote_pack", "pdf"],
        },
        "quote_pack_manifest": {
            "keys": ["quote_pack_manifest_path", "quotePackManifestPath"],
            "keywords": ["quote_pack", "manifest"],
        },
        "submission_manifest": {
            "keys": ["submission_package_manifest_path", "submissionManifestPath", "submissionPackageManifestPath"],
            "keywords": ["submission", "manifest"],
        },
        "tax_compliance": {
            "keys": ["tax_compliance_path", "taxCompliancePath"],
            "keywords": ["tax"],
        },
        "company_registration": {
            "keys": ["company_registration_path", "companyRegistrationPath", "registration_path"],
            "keywords": ["company", "registration"],
        },
        "bbbee": {
            "keys": ["bbbee_path", "bbbeePath"],
            "keywords": ["bbbee"],
        },
        "bank_confirmation": {
            "keys": ["bank_confirmation_path", "bankConfirmationPath", "bank_path"],
            "keywords": ["bank"],
        },
    }

    selected_paths: Dict[str, str] = {}
    required_artifacts: Dict[str, bool] = {}
    for key, spec in artifact_specs.items():
        selected = _pick_existing_path(detail, spec["keys"], spec["keywords"], candidate_paths)
        selected_paths[key] = selected
        required_artifacts[key] = bool(selected)

    return {
        "required_artifacts": required_artifacts,
        "required_artifact_files": selected_paths,
    }


def _human_approval_state(detail: Dict[str, Any]) -> Dict[str, Any]:
    sources = [
        detail,
        _safe_dict(detail.get("submission_package")),
        _safe_dict(detail.get("review_ready_bundle")),
        _safe_dict(_safe_dict(detail.get("review_ready_bundle")).get("raw_review")),
        _safe_dict(detail.get("approval_record")),
        _safe_dict(_safe_dict(_safe_dict(detail.get("review_ready_bundle")).get("raw_review")).get("approval_record")),
    ]
    approved_by = ""
    approved_at = ""
    approval_decision = ""
    manual_approval_recorded = False
    approved_by_operator = False

    for source in sources:
        if not isinstance(source, dict):
            continue
        approved_by = approved_by or _clean(source.get("approved_by") or source.get("operator_name"))
        approved_at = approved_at or _clean(source.get("approved_at"))
        approval_decision = approval_decision or _clean(source.get("approval_decision"))
        manual_approval_recorded = manual_approval_recorded or bool(source.get("manual_approval_recorded"))
        approved_by_operator = approved_by_operator or bool(source.get("approved_by_operator"))
        if not approved_at and bool(source.get("manual_approval_recorded")) and _clean(source.get("timestamp")):
            approved_at = _clean(source.get("timestamp"))
        if not approval_decision and _clean(source.get("status")) == "recorded":
            approval_decision = "approved"

    human_approval_present = bool(
        manual_approval_recorded
        and approved_by_operator
        and approved_by
        and approved_at
        and approval_decision.lower() == "approved"
    )
    return {
        "manual_approval_recorded": manual_approval_recorded,
        "approved_by_operator": approved_by_operator,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "approval_decision": approval_decision.lower(),
        "human_approval_present": human_approval_present,
    }


def build_submission_pack_object(detail: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(detail or {})
    submission_package = _safe_dict(payload.get("submission_package"))
    review_ready_bundle = _safe_dict(payload.get("review_ready_bundle"))
    governed_submission = _safe_dict(payload.get("governed_submission"))
    submission_execution = _safe_dict(payload.get("submission_execution"))
    tender_id = _clean(payload.get("tender_id") or payload.get("rfq_number") or payload.get("buyer_rfq_number") or "RFQ")

    artifact_map = _artifact_map(payload)
    required_artifacts = artifact_map["required_artifacts"]
    required_artifact_files = artifact_map["required_artifact_files"]
    missing_artifacts = [name for name, present in required_artifacts.items() if not present]
    blocking_codes = [f"missing_{name}" for name in missing_artifacts]
    approval_state = _human_approval_state(payload)

    final_submission_locked = bool(
        governed_submission.get("submissionLocked", submission_execution.get("submissionLocked", True))
    )
    approval_ready = not blocking_codes
    submission_ready = approval_ready and approval_state["human_approval_present"] and final_submission_locked
    if approval_ready and submission_ready:
        status = "ready"
    elif approval_ready:
        status = "approval_ready"
    elif blocking_codes:
        status = "blocked"
    else:
        status = "created"

    selected_files = _existing_unique(list(required_artifact_files.values()))
    readied_pack_files = _existing_unique(
        [
            _clean(submission_package.get("quote_pack_pdf_path") or submission_package.get("quotePackPdfPath")),
            _clean(submission_package.get("buyer_pricing_schedule_path") or submission_package.get("buyerPricingSchedulePath")),
            _clean(submission_package.get("quote_pack_manifest_path") or submission_package.get("quotePackManifestPath")),
            _clean(submission_package.get("submission_package_manifest_path") or submission_package.get("submissionManifestPath") or submission_package.get("submissionPackageManifestPath")),
            _clean(submission_package.get("submission_pack_object_path") or submission_package.get("submissionPackObjectPath")),
            _clean(submission_package.get("submission_pack_readiness_path") or submission_package.get("submissionPackReadinessPath")),
            _clean(submission_package.get("submission_pack_artifacts_path") or submission_package.get("submissionPackArtifactsPath")),
            _clean(submission_package.get("submission_pack_summary_path") or submission_package.get("submissionPackSummaryPath")),
        ]
    )
    artifact_count = len(_existing_unique(selected_files + readied_pack_files))
    readiness_score = int(round((len(required_artifacts) - len(missing_artifacts)) / max(len(required_artifacts), 1) * 100))

    created_at = _clean(
        submission_package.get("created_at")
        or submission_package.get("generated_at")
        or review_ready_bundle.get("created_at")
        or governing_timestamp(governed_submission, submission_execution)
        or _now_iso()
    )

    return {
        "status": status,
        "package_status": status,
        "approval_ready": approval_ready,
        "submission_ready": submission_ready,
        "approvalReady": approval_ready,
        "submissionReady": submission_ready,
        "manual_approval_recorded": approval_state["manual_approval_recorded"],
        "approved_by_operator": approval_state["approved_by_operator"],
        "approved_by": approval_state["approved_by"],
        "approved_at": approval_state["approved_at"],
        "approval_decision": approval_state["approval_decision"],
        "human_approval_present": approval_state["human_approval_present"],
        "final_submission_locked": final_submission_locked,
        "manual_submission_only": True,
        "required_artifacts": required_artifacts,
        "required_artifact_files": required_artifact_files,
        "missing_artifacts": missing_artifacts,
        "blocking_codes": blocking_codes,
        "readiness_score": readiness_score,
        "artifact_count": artifact_count,
        "created_at": created_at,
        "generated_at": created_at,
        "timestamp": _now_iso(),
    }


def governing_timestamp(governed_submission: Dict[str, Any], submission_execution: Dict[str, Any]) -> str:
    for candidate in (
        governed_submission.get("created_at"),
        governed_submission.get("generated_at"),
        submission_execution.get("created_at"),
        submission_execution.get("generated_at"),
    ):
        cleaned = _clean(candidate)
        if cleaned:
            return cleaned
    return ""


def _review_ready_bundle_dir(tender_id: str) -> Path:
    from app.core.runtime_paths import get_runtime_paths

    return get_runtime_paths().manual_production_dir / "review_ready_bundles" / tender_id


def _governed_submission_dir(tender_id: str) -> Path:
    from app.core.runtime_paths import get_runtime_paths

    return get_runtime_paths().manual_production_dir / "governed_submissions" / tender_id


def _operator_timeline_path() -> Path:
    from app.core.runtime_paths import get_runtime_paths

    return get_runtime_paths().manual_production_dir / "operator_timeline.jsonl"


def _append_review_bundle_audit_export(tender_id: str, event: Dict[str, Any]) -> None:
    path = _review_ready_bundle_dir(tender_id) / "audit_export.json"
    payload = _read_json(path)
    items = payload if isinstance(payload, list) else []
    items.append(
        {
            "id": f"audit-{event['timestamp']}",
            "event_type": "submission_pack_created",
            "source": "submission-package",
            "severity": "success" if event["status"] == "ready" else "info",
            "title": "Submission pack created",
            "message": f"Submission pack {event['status']} for {tender_id}",
            "buyer_rfq_number": tender_id,
            "quote_number": "",
            "payload": event,
            "created_at": event["timestamp"],
        }
    )
    _write_json(path, items)


def _append_governed_submission_audit_records(tender_id: str, event: Dict[str, Any]) -> None:
    workspace = _governed_submission_dir(tender_id)
    ledger_path = workspace / "immutable_audit_ledger.jsonl"
    timeline_path = workspace / "audit_replay_timeline.json"
    _write_jsonl(
        ledger_path,
        {
            "kind": "submission_pack_created",
            "timestamp": event["timestamp"],
            "payload": event,
        },
    )
    timeline = _read_json(timeline_path)
    items = timeline if isinstance(timeline, list) else []
    items.append(
        {
            "event_type": "submission_pack_created",
            "timestamp": event["timestamp"],
            "source": "submission-package",
            "details": event,
        }
    )
    _write_json(timeline_path, items)


def _append_operator_timeline(tender_id: str, event: Dict[str, Any]) -> None:
    _write_jsonl(
        _operator_timeline_path(),
        {
            "event_id": f"op-event-{tender_id}-{event['timestamp']}",
            "event_type": "submission_pack_created",
            "operator_id": "system",
            "tender_id": tender_id,
            "title": "Submission pack created",
            "severity": "success" if event["status"] == "ready" else "info",
            "reversible": False,
            "reviewable": True,
            "created_at": event["timestamp"],
            "details": event,
        },
    )


def _record_submission_pack_created_event(
    tender_id: str,
    pack: Dict[str, Any],
    *,
    runtime_dir: Optional[str] = None,
) -> Dict[str, Any]:
    event = {
        "event": "submission_pack_created",
        "rfq": _clean(tender_id),
        "timestamp": _now_iso(),
        "artifact_count": int(pack.get("artifact_count") or 0),
        "readiness_score": int(pack.get("readiness_score") or 0),
        "status": _clean(pack.get("status") or "created"),
        "blocking_codes": list(pack.get("blocking_codes") or []),
        "approval_ready": bool(pack.get("approval_ready")),
        "submission_ready": bool(pack.get("submission_ready")),
    }
    _write_jsonl(_submission_pack_audit_log(runtime_dir), event)
    _append_review_bundle_audit_export(tender_id, event)
    _append_governed_submission_audit_records(tender_id, event)
    _append_operator_timeline(tender_id, event)
    try:
        append_audit_event(
            event_type="submission_pack_created",
            source="submission-package",
            severity="success" if event["status"] == "ready" else "info",
            title="Submission pack created",
            message=f"Submission pack {event['status']} for {event['rfq']}",
            buyer_rfq_number=event["rfq"],
            payload=event,
            runtime_dir=runtime_dir,
        )
    except Exception:
        pass
    return event


def get_submission_pack_measurement_metrics(limit: int = 1000, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    events = [
        item
        for item in _read_jsonl(_submission_pack_audit_log(runtime_dir))[-max(1, int(limit or 1000)) :]
        if _clean(item.get("event")) == "submission_pack_created"
    ]
    created_count = len(events)
    ready_count = len([item for item in events if _clean(item.get("status")) == "ready" or bool(item.get("submission_ready"))])
    blocked_count = len([item for item in events if _clean(item.get("status")) == "blocked" or bool(item.get("blocking_codes"))])
    average_readiness_score = round(sum(int(item.get("readiness_score") or 0) for item in events) / created_count, 2) if created_count else 0.0
    blocking_code_counts: Dict[str, int] = {}
    for item in events:
        for code in item.get("blocking_codes") or []:
            cleaned = _clean(code)
            if not cleaned:
                continue
            blocking_code_counts[cleaned] = blocking_code_counts.get(cleaned, 0) + 1
    top_blocking_codes = [
        {"code": code, "count": count}
        for code, count in sorted(blocking_code_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "status": "ok",
        "submission_pack_created_count": created_count,
        "submission_pack_ready_count": ready_count,
        "submission_pack_blocked_count": blocked_count,
        "submission_pack_success_rate": round((ready_count / created_count) * 100.0, 2) if created_count else 0.0,
        "submission_pack_block_rate": round((blocked_count / created_count) * 100.0, 2) if created_count else 0.0,
        "average_readiness_score": average_readiness_score,
        "top_blocking_codes": top_blocking_codes,
        "log_file": str(_submission_pack_audit_log(runtime_dir)),
        "updated_at": _now_iso(),
    }


def evaluate_submission_gate(detail: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(detail or {})
    pack = _safe_dict(payload.get("submission_pack"))
    package = _safe_dict(payload.get("submission_package"))
    review_ready_bundle = _safe_dict(payload.get("review_ready_bundle"))
    governed_submission = _safe_dict(payload.get("governed_submission"))
    submission_execution = _safe_dict(payload.get("submission_execution"))

    if pack:
        approval_ready = bool(pack.get("approval_ready"))
        submission_ready = bool(pack.get("submission_ready")) and approval_ready
        blockers = list(pack.get("blocking_codes") or [])
        if approval_ready and not bool(pack.get("human_approval_present")):
            blockers.append("human approval required")
        if governed_submission and not bool(governed_submission.get("submissionLocked", True)):
            blockers.append("final_submission_not_locked")
        if submission_execution and _clean(submission_execution.get("execution_status")).lower() not in {"", "ok", "executed", "ready"}:
            blockers.append("submission execution not ready")
        return {
            "status": "ok" if not blockers else "blocked",
            "tender_id": _clean(payload.get("tender_id")),
            "approval_ready": approval_ready,
            "submission_ready": submission_ready,
            "blocking_issues": blockers,
            "allowed": not blockers,
            "package_status": _clean(pack.get("status") or ("ready" if not blockers else "blocked")),
        }

    approval_ready = bool(package.get("approval_ready")) and bool(review_ready_bundle.get("review_ready"))
    submission_ready = bool(package.get("submission_ready")) and approval_ready
    blockers: List[str] = []
    if not approval_ready:
        blockers.append("approval_ready must be true")
    if not submission_ready:
        blockers.append("submission_ready must be true")
    if governed_submission and not bool(governed_submission.get("submissionLocked", True)):
        blockers.append("submission must be locked before final release")
    if submission_execution and _clean(submission_execution.get("execution_status")).lower() not in {"", "ok", "executed", "ready"}:
        blockers.append("submission execution not ready")

    allowed = not blockers
    return {
        "status": "ok" if allowed else "blocked",
        "tender_id": _clean(payload.get("tender_id")),
        "approval_ready": approval_ready,
        "submission_ready": submission_ready,
        "blocking_issues": blockers,
        "allowed": allowed,
        "package_status": _clean(package.get("package_status") or ("ready" if allowed else "blocked")),
    }


def build_submission_package(detail: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(detail or {})
    tender_id = _clean(payload.get("tender_id") or payload.get("rfq_number") or payload.get("buyer_rfq_number") or "RFQ")
    workspace = _submission_package_workspace(tender_id)
    workspace.mkdir(parents=True, exist_ok=True)

    package = _safe_dict(payload.get("submission_package"))
    quote_pack_pdf = _clean(package.get("quote_pack_pdf_path") or package.get("quotePackPdfPath") or workspace / f"{tender_id}__quote_pack.pdf")
    quote_pack_json = _clean(package.get("quote_pack_json_path") or package.get("quotePackJsonPath") or workspace / f"{tender_id}__quote_pack.json")
    buyer_schedule = _clean(package.get("buyer_pricing_schedule_path") or package.get("buyerPricingSchedulePath") or workspace / f"{tender_id}__buyer_pricing_schedule.csv")
    quote_pack_manifest = _clean(package.get("quote_pack_manifest_path") or package.get("quotePackManifestPath") or workspace / f"{tender_id}__quote_pack_manifest.json")
    submission_manifest = _clean(package.get("submission_package_manifest_path") or package.get("submissionManifestPath") or package.get("submissionPackageManifestPath") or workspace / f"{tender_id}__submission_package_manifest.json")
    zip_path = _clean(package.get("zip_path") or package.get("zipPath") or workspace / f"{tender_id}__submission_package.zip")
    submission_pack_object_path = _clean(package.get("submission_pack_object_path") or workspace / f"{tender_id}__submission_pack_object.json")
    submission_pack_readiness_path = _clean(package.get("submission_pack_readiness_path") or workspace / f"{tender_id}__submission_pack_readiness.json")
    submission_pack_artifacts_path = _clean(package.get("submission_pack_artifacts_path") or workspace / f"{tender_id}__submission_pack_artifacts.json")
    submission_pack_summary_path = _clean(package.get("submission_pack_summary_path") or workspace / f"{tender_id}__submission_pack_summary.json")

    file_specs = (
        (quote_pack_pdf, "quote pack"),
        (quote_pack_json, json.dumps({"tender_id": tender_id, "status": "ready"}, indent=2)),
        (buyer_schedule, "line_no,description,quantity,unit_price,line_total\n"),
        (quote_pack_manifest, json.dumps({"tender_id": tender_id, "package_status": "ready"}, indent=2)),
        (submission_manifest, json.dumps({"tender_id": tender_id, "package_status": "ready"}, indent=2)),
        (submission_pack_object_path, json.dumps({"tender_id": tender_id, "artifact_type": "submission_pack_object"}, indent=2)),
        (submission_pack_readiness_path, json.dumps({"tender_id": tender_id, "artifact_type": "submission_pack_readiness"}, indent=2)),
        (submission_pack_artifacts_path, json.dumps({"tender_id": tender_id, "artifact_type": "submission_pack_artifacts"}, indent=2)),
        (submission_pack_summary_path, json.dumps({"tender_id": tender_id, "artifact_type": "submission_pack_summary"}, indent=2)),
        (zip_path, "zip placeholder"),
    )

    created_any = False
    for raw_path, content in file_specs:
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            created_any = True

    assembler_result = _build_submission_pack(
        {
            "rfq_number": tender_id,
            "reference_number": tender_id,
            "title": payload.get("title") or tender_id,
            "buyer_name": payload.get("buyer_name") or payload.get("buyer") or "",
            "rendered_buyer_pdf_path": quote_pack_pdf,
            "quote_pack_pdf_path": quote_pack_pdf,
            "review_rows": _safe_list(payload.get("review_rows")),
            "metadata": {
                "buyer_rfq_number": tender_id,
                "title": payload.get("title") or tender_id,
                "buyer_name": payload.get("buyer_name") or payload.get("buyer") or "",
                "pdf_output_dir": str(workspace),
                "compliance_document_paths": _safe_list(payload.get("compliance_document_paths")),
                "extra_submission_paths": _safe_list(payload.get("extra_submission_paths")),
            },
        }
    )

    submission_pack = build_submission_pack_object(
        {
            **payload,
            "tender_id": tender_id,
            "submission_package": {
                **package,
                "quote_pack_pdf_path": quote_pack_pdf,
                "quote_pack_json_path": quote_pack_json,
                "buyer_pricing_schedule_path": buyer_schedule,
                "quote_pack_manifest_path": quote_pack_manifest,
                "submission_package_manifest_path": submission_manifest,
                "submission_pack_object_path": submission_pack_object_path,
                "submission_pack_readiness_path": submission_pack_readiness_path,
                "submission_pack_artifacts_path": submission_pack_artifacts_path,
                "submission_pack_summary_path": submission_pack_summary_path,
                "zip_path": zip_path,
                "submission_pack_files": assembler_result.get("submission_pack_files") or [],
                "source_quote_file_count": int(payload.get("source_quote_file_count") or 0),
                "created_at": payload.get("created_at") or payload.get("generated_at") or _now_iso(),
            },
            "review_ready_bundle": payload.get("review_ready_bundle") or {},
            "governed_submission": payload.get("governed_submission") or {},
            "submission_execution": payload.get("submission_execution") or {},
        }
    )

    if created_any:
        _record_submission_pack_created_event(tender_id, submission_pack)

    return {
        "status": "ok",
        "tender_id": tender_id,
        "approval_ready": bool(submission_pack.get("approval_ready")),
        "submission_ready": bool(submission_pack.get("submission_ready")),
        "approvalReady": bool(submission_pack.get("approval_ready")),
        "submissionReady": bool(submission_pack.get("submission_ready")),
        "package_status": submission_pack.get("status") or ("ready" if submission_pack.get("submission_ready") else "review_required"),
        "quality_score": 1.0 if submission_pack.get("submission_ready") else 0.0,
        "quality_status": "healthy" if submission_pack.get("submission_ready") else "degraded",
        "quality_notes": [] if submission_pack.get("submission_ready") else ["submission package not ready"],
        "warnings": list(payload.get("warnings") or []),
        "blocking_issues": list(submission_pack.get("blocking_codes") or []),
        "missing_artifacts": list(submission_pack.get("missing_artifacts") or []),
        "download_url": f"/operations/rfqs/{tender_id}/submission-package/download",
        "metadata_url": submission_manifest,
        "quote_pack_pdf_path": quote_pack_pdf,
        "quote_pack_json_path": quote_pack_json,
        "buyer_pricing_schedule_path": buyer_schedule,
        "quote_pack_manifest_path": quote_pack_manifest,
        "submissionManifestPath": submission_manifest,
        "submission_package_manifest_path": submission_manifest,
        "zip_path": zip_path,
        "downloadUrl": f"/operations/rfqs/{tender_id}/submission-package/download",
        "metadataUrl": submission_manifest,
        "quotePackPdfPath": quote_pack_pdf,
        "quotePackJsonPath": quote_pack_json,
        "buyerPricingSchedulePath": buyer_schedule,
        "quotePackManifestPath": quote_pack_manifest,
        "submissionPackageManifestPath": submission_manifest,
        "submissionPackObjectPath": submission_pack_object_path,
        "submissionPackReadinessPath": submission_pack_readiness_path,
        "submissionPackArtifactsPath": submission_pack_artifacts_path,
        "submissionPackSummaryPath": submission_pack_summary_path,
        "zipPath": zip_path,
        "source_quote_file_count": int(payload.get("source_quote_file_count") or 0),
        "submission_pack_ready_count": int(assembler_result.get("submission_pack_ready_count") or 0),
        "submission_pack_files": assembler_result.get("submission_pack_files") or [],
        "review_ready_bundle": payload.get("review_ready_bundle") or {},
        "gate": evaluate_submission_gate({**payload, "submission_pack": submission_pack}),
        "created_at": submission_pack.get("created_at") or payload.get("created_at") or payload.get("generated_at") or "",
        "submission_pack": submission_pack,
    }
