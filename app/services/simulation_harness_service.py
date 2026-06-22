from __future__ import annotations
from app.services.simulation_lane_metrics import calculate_lane_metrics
import json
import os
import shutil
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence

from app.core.runtime_paths import get_runtime_paths
from app.qualification.qualification_engine import qualify_rfq
from app.services import audit_trail_service, manual_approval_service, submission_review_service
from app.services.submission_package_service import build_submission_package


AUDIT_SINK_NAMES = (
    "submission_pack_events",
    "audit_export",
    "governed_ledger",
    "replay_timeline",
    "operator_timeline",
    "audit_trail",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _slug(value: str) -> str:
    text = _clean(value)
    if not text:
        return "RFQ"
    normalized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in text)
    normalized = normalized.strip("-_")
    return normalized or "RFQ"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not path.exists():
        return items
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                items.append(payload)
    except Exception:
        return []
    return items


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _fixture_corpus(project_root: Path) -> List[Path]:
    roots = (
        project_root / "tests" / "fixtures" / "rfqs",
        project_root / "tests" / "fixtures" / "real_pilot_rfqs",
    )
    files: List[Path] = []
    for root in roots:
        if root.exists():
            files.extend(sorted(root.glob("*.json")))
    return files


def _load_fixture(path: Path) -> Dict[str, Any]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"fixture is not a JSON object: {path}")
    return payload


def _expected_qualified(fixture: Dict[str, Any]) -> bool:
    excluded = _clean(fixture.get("expected_exclusion_status")).lower() == "excluded"
    below_margin = _clean(fixture.get("expected_minimum_profit_result")).lower() == "below_margin"
    return not excluded and not below_margin


def _build_submission_instructions(fixture: Dict[str, Any]) -> str:
    text = "Submit by email to bids@example.com."
    if _clean(fixture.get("expected_exclusion_status")).lower() == "excluded":
        return text
    if "briefing" in _clean(fixture.get("title")).lower():
        return "Mandatory briefing session required before submission. Submit by email to bids@example.com."
    return text


def _build_extracted_text(fixture: Dict[str, Any]) -> str:
    title = _clean(fixture.get("title"))
    category = _clean(fixture.get("category"))
    item_descriptions = ", ".join(_clean(item.get("description")) for item in _safe_list(fixture.get("line_items")) if isinstance(item, dict))
    buyer_schedule = _safe_dict(fixture.get("buyer_pricing_schedule"))
    schedule_text = "pricing schedule attached" if buyer_schedule else "pricing schedule available"
    return " ".join(
        part
        for part in (
            title,
            category,
            item_descriptions,
            schedule_text,
            "SBD4 SBD6.1 CSD BBBEE quotation on company letterhead",
            _build_submission_instructions(fixture),
        )
        if part
    )


def _qualification_payload(fixture: Dict[str, Any], rfq_id: str) -> Dict[str, Any]:
    above_margin = _clean(fixture.get("expected_minimum_profit_result")).lower() != "below_margin"
    estimated_profit = 50000.0 if above_margin else 25000.0
    return {
        "tender_id": rfq_id,
        "title": _clean(fixture.get("title")) or rfq_id,
        "buyer_name": _clean(fixture.get("buyer_name")) or "Historical RFQ Corpus",
        "category": fixture.get("category") or "",
        "submission_instructions": _build_submission_instructions(fixture),
        "extracted_text": _build_extracted_text(fixture),
        "estimated_profit": estimated_profit,
        "gross_margin_ratio": 0.3,
        "estimated_contract_value": round(estimated_profit / 0.25, 2),
    }


def _resolve_fixture_artifacts(fixture_path: Path, fixture: Dict[str, Any]) -> List[str]:
    resolved: List[str] = []
    for key in ("source_files",):
        for raw in _safe_list(fixture.get(key)):
            candidate = (fixture_path.parent / _clean(raw)).resolve()
            if candidate.exists():
                resolved.append(str(candidate))
    pricing_file = _clean(fixture.get("pricing_file"))
    if pricing_file:
        candidate = (fixture_path.parent / pricing_file).resolve()
        if candidate.exists():
            resolved.append(str(candidate))
    return resolved


def _compliance_source_candidates(project_root: Path) -> Dict[str, List[Path]]:
    return {
        "tax_compliance.pdf": [
            project_root / "runtime" / "compliance" / "tax_compliance.pdf",
            project_root / "runtime" / "manual_production" / "submission_packages" / "PAPER-POSITIVE-001" / "tax_compliance.pdf",
            project_root / "runtime" / "manual_production" / "submission_packages" / "PAPER" / "tax_compliance.pdf",
        ],
        "company_registration.pdf": [
            project_root / "runtime" / "compliance" / "company_registration.pdf",
            project_root / "runtime" / "manual_production" / "submission_packages" / "PAPER-POSITIVE-001" / "company_registration.pdf",
            project_root / "runtime" / "manual_production" / "submission_packages" / "PAPER" / "company_registration.pdf",
        ],
        "bbbee_certificate.pdf": [
            project_root / "runtime" / "compliance" / "bbbee_certificate.pdf",
            project_root / "runtime" / "manual_production" / "submission_packages" / "PAPER-POSITIVE-001" / "bbbee_certificate.pdf",
            project_root / "runtime" / "manual_production" / "submission_packages" / "PAPER" / "bbbee_certificate.pdf",
        ],
        "bank_confirmation.pdf": [
            project_root / "runtime" / "compliance" / "bank_confirmation.pdf",
            project_root / "runtime" / "manual_production" / "submission_packages" / "PAPER-POSITIVE-001" / "bank_confirmation.pdf",
            project_root / "runtime" / "manual_production" / "submission_packages" / "PAPER" / "bank_confirmation.pdf",
        ],
    }


def _resolve_compliance_sources(project_root: Path) -> Dict[str, Path]:
    resolved: Dict[str, Path] = {}
    for filename, candidates in _compliance_source_candidates(project_root).items():
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                resolved[filename] = candidate.resolve()
                break
    missing = [name for name in _compliance_source_candidates(project_root) if name not in resolved]
    if missing:
        raise FileNotFoundError(f"missing compliance source files for simulation harness: {', '.join(missing)}")
    return resolved


def _missing_compliance_name(fixture_path: Path) -> str:
    name = fixture_path.stem.lower()
    if "incomplete" in name:
        return "bank_confirmation.pdf"
    if "messy" in name:
        return "company_registration.pdf"
    if "missing_source" in name:
        return "tax_compliance.pdf"
    return "bank_confirmation.pdf"


def _stage_compliance_documents(
    *,
    project_root: Path,
    package_dir: Path,
    fixture_path: Path,
    expected_submission_ready: bool,
) -> List[str]:
    package_dir.mkdir(parents=True, exist_ok=True)
    sources = _resolve_compliance_sources(project_root)
    omit_name = "" if expected_submission_ready else _missing_compliance_name(fixture_path)
    staged: List[str] = []
    for filename, source_path in sources.items():
        if filename == omit_name:
            continue
        destination = package_dir / filename
        shutil.copy2(source_path, destination)
        staged.append(str(destination))
    return staged


@contextmanager
def _isolated_runtime(project_root: Path, runtime_root: Path) -> Iterator[None]:
    original_env = {key: os.environ.get(key) for key in ("LMCP_PROJECT_ROOT", "LMCP_RUNTIME_DIR", "LMCP_MANUAL_PRODUCTION_DIR")}
    original_audit = (
        audit_trail_service.RUNTIME_DIR,
        audit_trail_service.AUDIT_DIR,
        audit_trail_service.AUDIT_FILE,
    )
    original_approval = (
        manual_approval_service.RUNTIME_DIR,
        manual_approval_service.MANUAL_PRODUCTION_DIR,
        manual_approval_service.APPROVAL_LOG_FILE,
    )
    original_review = (
        submission_review_service.RUNTIME_DIR,
        submission_review_service.MANUAL_PRODUCTION_DIR,
        submission_review_service.SUBMISSION_REVIEW_LOG_FILE,
    )

    manual_dir = runtime_root / "manual_production"
    os.environ["LMCP_PROJECT_ROOT"] = str(project_root)
    os.environ["LMCP_RUNTIME_DIR"] = str(runtime_root)
    os.environ["LMCP_MANUAL_PRODUCTION_DIR"] = str(manual_dir)
    get_runtime_paths.cache_clear()

    audit_trail_service.RUNTIME_DIR = runtime_root
    audit_trail_service.AUDIT_DIR = runtime_root / "audit_trail"
    audit_trail_service.AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_trail_service.AUDIT_FILE = audit_trail_service.AUDIT_DIR / "audit_events.json"

    manual_approval_service.RUNTIME_DIR = runtime_root
    manual_approval_service.MANUAL_PRODUCTION_DIR = manual_dir
    manual_approval_service.MANUAL_PRODUCTION_DIR.mkdir(parents=True, exist_ok=True)
    manual_approval_service.APPROVAL_LOG_FILE = manual_dir / "approvals.jsonl"

    submission_review_service.RUNTIME_DIR = runtime_root
    submission_review_service.MANUAL_PRODUCTION_DIR = manual_dir
    submission_review_service.SUBMISSION_REVIEW_LOG_FILE = manual_dir / "submission_reviews.jsonl"

    try:
        get_runtime_paths().ensure_directories()
        yield
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        audit_trail_service.RUNTIME_DIR, audit_trail_service.AUDIT_DIR, audit_trail_service.AUDIT_FILE = original_audit
        manual_approval_service.RUNTIME_DIR, manual_approval_service.MANUAL_PRODUCTION_DIR, manual_approval_service.APPROVAL_LOG_FILE = original_approval
        submission_review_service.RUNTIME_DIR, submission_review_service.MANUAL_PRODUCTION_DIR, submission_review_service.SUBMISSION_REVIEW_LOG_FILE = original_review
        get_runtime_paths.cache_clear()


def _submission_pack_event_counts(runtime_root: Path, rfq_id: str) -> Dict[str, int]:
    manual_dir = runtime_root / "manual_production"
    review_dir = manual_dir / "review_ready_bundles" / rfq_id
    governed_dir = manual_dir / "governed_submissions" / rfq_id

    submission_pack_events = sum(1 for item in _read_jsonl(manual_dir / "submission_pack_events.jsonl") if _clean(item.get("event")) == "submission_pack_created" and _clean(item.get("rfq")) == rfq_id)
    audit_export = sum(1 for item in _safe_list(_read_json(review_dir / "audit_export.json")) if isinstance(item, dict) and _clean(item.get("event_type")) == "submission_pack_created" and _clean(item.get("buyer_rfq_number")) == rfq_id)
    governed_ledger = sum(1 for item in _read_jsonl(governed_dir / "immutable_audit_ledger.jsonl") if _clean(item.get("kind")) == "submission_pack_created" and _clean(_safe_dict(item.get("payload")).get("rfq")) == rfq_id)
    replay_timeline = sum(1 for item in _safe_list(_read_json(governed_dir / "audit_replay_timeline.json")) if isinstance(item, dict) and _clean(item.get("event_type")) == "submission_pack_created" and _clean(_safe_dict(item.get("details")).get("rfq")) == rfq_id)
    operator_timeline = sum(1 for item in _read_jsonl(manual_dir / "operator_timeline.jsonl") if _clean(item.get("event_type")) == "submission_pack_created" and _clean(item.get("tender_id")) == rfq_id)
    audit_trail = sum(1 for item in _safe_list(_read_json(runtime_root / "audit_trail" / "audit_events.json")) if isinstance(item, dict) and _clean(item.get("event_type")) == "submission_pack_created" and _clean(item.get("buyer_rfq_number")) == rfq_id)

    return {
        "submission_pack_events": submission_pack_events,
        "audit_export": audit_export,
        "governed_ledger": governed_ledger,
        "replay_timeline": replay_timeline,
        "operator_timeline": operator_timeline,
        "audit_trail": audit_trail,
    }


def _audit_integrity_for_rfq(runtime_root: Path, rfq_id: str) -> Dict[str, Any]:
    sink_counts = _submission_pack_event_counts(runtime_root, rfq_id)
    missing = sum(1 for count in sink_counts.values() if count == 0)
    duplicates = sum(max(0, count - 1) for count in sink_counts.values())
    return {
        "sink_counts": sink_counts,
        "audit_events_missing": missing,
        "duplicate_audit_events": duplicates,
        "audit_integrity": missing == 0 and duplicates == 0 and all(count == 1 for count in sink_counts.values()),
    }


def _orphaned_audit_events(runtime_root: Path, valid_rfq_ids: set[str]) -> Dict[str, List[str]]:
    manual_dir = runtime_root / "manual_production"
    orphaned: Dict[str, List[str]] = {name: [] for name in AUDIT_SINK_NAMES}

    for item in _read_jsonl(manual_dir / "submission_pack_events.jsonl"):
        rfq = _clean(item.get("rfq"))
        if rfq and rfq not in valid_rfq_ids:
            orphaned["submission_pack_events"].append(rfq)

    for item in _safe_list(_read_json(runtime_root / "audit_trail" / "audit_events.json")):
        if not isinstance(item, dict):
            continue
        if _clean(item.get("event_type")) != "submission_pack_created":
            continue
        rfq = _clean(item.get("buyer_rfq_number"))
        if rfq and rfq not in valid_rfq_ids:
            orphaned["audit_trail"].append(rfq)

    for item in _read_jsonl(manual_dir / "operator_timeline.jsonl"):
        if _clean(item.get("event_type")) != "submission_pack_created":
            continue
        rfq = _clean(item.get("tender_id"))
        if rfq and rfq not in valid_rfq_ids:
            orphaned["operator_timeline"].append(rfq)

    review_root = manual_dir / "review_ready_bundles"
    if review_root.exists():
        for bundle_dir in review_root.iterdir():
            if not bundle_dir.is_dir():
                continue
            for item in _safe_list(_read_json(bundle_dir / "audit_export.json")):
                if not isinstance(item, dict):
                    continue
                if _clean(item.get("event_type")) != "submission_pack_created":
                    continue
                rfq = _clean(item.get("buyer_rfq_number"))
                if rfq and rfq not in valid_rfq_ids:
                    orphaned["audit_export"].append(rfq)

    governed_root = manual_dir / "governed_submissions"
    if governed_root.exists():
        for governed_dir in governed_root.iterdir():
            if not governed_dir.is_dir():
                continue
            for item in _read_jsonl(governed_dir / "immutable_audit_ledger.jsonl"):
                if _clean(item.get("kind")) != "submission_pack_created":
                    continue
                rfq = _clean(_safe_dict(item.get("payload")).get("rfq"))
                if rfq and rfq not in valid_rfq_ids:
                    orphaned["governed_ledger"].append(rfq)
            for item in _safe_list(_read_json(governed_dir / "audit_replay_timeline.json")):
                if not isinstance(item, dict):
                    continue
                if _clean(item.get("event_type")) != "submission_pack_created":
                    continue
                rfq = _clean(_safe_dict(item.get("details")).get("rfq"))
                if rfq and rfq not in valid_rfq_ids:
                    orphaned["replay_timeline"].append(rfq)

    return {key: sorted(set(values)) for key, values in orphaned.items()}


def _top_code_counts(counter: Counter[str]) -> List[Dict[str, Any]]:
    return [{"code": code, "count": count} for code, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))]


def run_simulation_harness(
    *,
    max_rfqs: int = 100,
    fixture_paths: Optional[Sequence[str | Path]] = None,
    inject_approvals_for: Optional[Sequence[str]] = None,
    run_label: str = "",
) -> Dict[str, Any]:
    if max_rfqs < 1:
        raise ValueError("max_rfqs must be at least 1")

    runtime_paths = get_runtime_paths()
    project_root = runtime_paths.project_root
    corpus = [Path(path).resolve() for path in fixture_paths] if fixture_paths else _fixture_corpus(project_root)
    if not corpus:
        raise FileNotFoundError("no RFQ fixtures available for simulation")

    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    label = _slug(run_label) if _clean(run_label) else "simulation"
    run_id = f"{label}-{run_timestamp}"
    run_root = runtime_paths.runtime_root / "simulation_runs" / run_id
    isolated_runtime_root = run_root / "isolated_runtime"
    run_root.mkdir(parents=True, exist_ok=True)

    approval_markers = {_clean(item) for item in inject_approvals_for or [] if _clean(item)}
    selected_fixture_paths = [corpus[index % len(corpus)] for index in range(max_rfqs)]
    manifest = {
        "run_id": run_id,
        "created_at": _now_iso(),
        "requested_rfqs": max_rfqs,
        "selected_rfqs": len(selected_fixture_paths),
        "fixture_corpus_size": len(corpus),
        "corpus_strategy": "cycled_labeled_historical_fixtures",
        "feature_freeze_mode": True,
        "portal_submission_enabled": False,
        "manual_submission_only": True,
        "approval_injections": sorted(approval_markers),
        "fixture_files": [str(path) for path in selected_fixture_paths],
        "isolated_runtime_root": str(isolated_runtime_root),
    }

    results: List[Dict[str, Any]] = []
    rejection_codes = Counter[str]()
    blocking_codes = Counter[str]()

    with _isolated_runtime(project_root, isolated_runtime_root):
        for index, fixture_path in enumerate(selected_fixture_paths, start=1):
            fixture = _load_fixture(fixture_path)
            base_tender_id = _clean(fixture.get("tender_id")) or fixture_path.stem.upper()
            rfq_id = f"{_slug(base_tender_id)}-SIM-{index:03d}"
            expected_submission_ready = bool(fixture.get("expected_submission_ready"))
            expected_qualified = _expected_qualified(fixture)
            qualification = qualify_rfq(_qualification_payload(fixture, rfq_id))
            qualification_status = _clean(qualification.get("qualification_status")).lower()
            qualified = qualification_status in {"qualified", "review_required"} or bool(qualification.get("quote_candidate"))
            approved = base_tender_id in approval_markers or rfq_id in approval_markers

            result: Dict[str, Any] = {
                "rfq_id": rfq_id,
                "base_tender_id": base_tender_id,
                "fixture_path": str(fixture_path),
                "harvested": True,
                "qualified": qualified,
                "qualification_status": qualification_status or ("qualified" if qualified else "rejected"),
                "qualification_expected": expected_qualified,
                "qualification_accurate": qualified == expected_qualified,
                "rejection_codes": list(qualification.get("rejection_codes") or []),
                "quote_pack_generated": False,
                "submission_pack_generated": False,
                "submission_pack_status": "not_generated",
                "approval_ready": False,
                "submission_ready": False,
                "human_approval_injected": approved,
                "readiness_score": 0,
                "blocking_codes": [],
                "audit_integrity": True,
                "audit_event_counts": {name: 0 for name in AUDIT_SINK_NAMES},
                "audit_events_missing": 0,
                "duplicate_audit_events": 0,
                "source_artifacts": _resolve_fixture_artifacts(fixture_path, fixture),
            }

            for code in result["rejection_codes"]:
                cleaned = _clean(code)
                if cleaned:
                    rejection_codes[cleaned] += 1

            if not qualified:
                results.append(result)
                continue

            package_dir = get_runtime_paths().manual_production_dir / "submission_packages" / rfq_id
            staged_docs = _stage_compliance_documents(
                project_root=project_root,
                package_dir=package_dir,
                fixture_path=fixture_path,
                expected_submission_ready=expected_submission_ready,
            )
            detail = {
                "tender_id": rfq_id,
                "title": _clean(fixture.get("title")) or rfq_id,
                "buyer_name": _clean(fixture.get("buyer_name")) or "Historical RFQ Corpus",
                "review_ready_bundle": {"review_ready": True, "submission_ready": False},
                "governed_submission": {"submissionLocked": True},
                "submission_execution": {"submissionLocked": True, "execution_status": "ready"},
                "compliance_document_paths": staged_docs,
                "extra_submission_paths": list(result["source_artifacts"]) + staged_docs,
            }
            if approved:
                detail.update(
                    {
                        "manual_approval_recorded": True,
                        "approved_by_operator": True,
                        "approved_by": "Simulation Operator",
                        "approved_at": _now_iso(),
                        "approval_decision": "approved",
                    }
                )

            package = build_submission_package(detail)
            pack = deepcopy(_safe_dict(package.get("submission_pack")))
            audit = _audit_integrity_for_rfq(get_runtime_paths().runtime_root, rfq_id)

            result.update(
                {
                    "quote_pack_generated": Path(_clean(package.get("quote_pack_pdf_path"))).exists() and Path(_clean(package.get("quote_pack_json_path"))).exists(),
                    "submission_pack_generated": True,
                    "submission_pack_status": _clean(pack.get("status")) or "created",
                    "approval_ready": bool(pack.get("approval_ready")),
                    "submission_ready": bool(pack.get("submission_ready")),
                    "readiness_score": int(pack.get("readiness_score") or 0),
                    "blocking_codes": list(pack.get("blocking_codes") or []),
                    "audit_integrity": bool(audit.get("audit_integrity")),
                    "audit_event_counts": audit["sink_counts"],
                    "audit_events_missing": int(audit.get("audit_events_missing") or 0),
                    "duplicate_audit_events": int(audit.get("duplicate_audit_events") or 0),
                }
            )
            for code in result["blocking_codes"]:
                cleaned = _clean(code)
                if cleaned:
                    blocking_codes[cleaned] += 1

            results.append(result)

        valid_rfq_ids = {item["rfq_id"] for item in results}
        orphaned = _orphaned_audit_events(get_runtime_paths().runtime_root, valid_rfq_ids)

    harvested_count = len(results)
    qualified_items = [item for item in results if item["qualified"]]
    rejected_items = [item for item in results if not item["qualified"]]
    generated_packs = [item for item in results if item["submission_pack_generated"]]
    approval_ready_items = [item for item in generated_packs if item["approval_ready"]]
    blocked_items = [item for item in generated_packs if item["blocking_codes"]]
    approved_items = [item for item in generated_packs if item["submission_ready"]]
    qualification_accurate_count = len([item for item in results if item["qualification_accurate"]])
    audit_events_emitted = sum(sum(int(count) for count in item["audit_event_counts"].values()) for item in generated_packs)
    audit_events_missing = sum(int(item["audit_events_missing"]) for item in generated_packs)
    duplicate_audit_events = sum(int(item["duplicate_audit_events"]) for item in generated_packs)
    orphaned_audit_events = sum(len(values) for values in orphaned.values())
    bypass_count = len([item for item in generated_packs if item["submission_ready"] and not item["human_approval_injected"]])
    average_readiness_score = round(sum(int(item["readiness_score"] or 0) for item in generated_packs) / len(generated_packs), 2) if generated_packs else 0.0

    metrics = {
        "harvested_count": harvested_count,
        "qualified_count": len(qualified_items),
        "rejected_count": len(rejected_items),
        "quote_packs_generated": len([item for item in generated_packs if item["quote_pack_generated"]]),
        "submission_packs_generated": len(generated_packs),
        "submission_packs_blocked": len(blocked_items),
        "submission_packs_approved": len(approved_items),
        "qualification_success_rate": round((len(qualified_items) / harvested_count) * 100.0, 2) if harvested_count else 0.0,
        "qualification_reject_rate": round((len(rejected_items) / harvested_count) * 100.0, 2) if harvested_count else 0.0,
        "qualification_accuracy": round((qualification_accurate_count / harvested_count) * 100.0, 2) if harvested_count else 0.0,
        "top_rejection_codes": _top_code_counts(rejection_codes),
        "submission_pack_success_rate": round((len(approval_ready_items) / len(generated_packs)) * 100.0, 2) if generated_packs else 0.0,
        "submission_pack_block_rate": round((len(blocked_items) / len(generated_packs)) * 100.0, 2) if generated_packs else 0.0,
        "average_readiness_score": average_readiness_score,
        "top_blocking_codes": _top_code_counts(blocking_codes),
        "approval_gate_bypass_count": bypass_count,
        "submission_ready_without_approval_count": bypass_count,
        "audit_events_emitted": audit_events_emitted,
        "audit_events_missing": audit_events_missing,
        "duplicate_audit_events": duplicate_audit_events,
        "orphaned_audit_events": orphaned_audit_events,
        "audit_integrity_failures": len([item for item in generated_packs if not item["audit_integrity"]]),
    }

    audit_summary = {
        "run_id": run_id,
        "generated_submission_pack_count": len(generated_packs),
        "expected_event_copies_per_submission_pack": len(AUDIT_SINK_NAMES),
        "audit_events_emitted": audit_events_emitted,
        "audit_events_missing": audit_events_missing,
        "duplicate_audit_events": duplicate_audit_events,
        "orphaned_audit_events": orphaned_audit_events,
        "orphaned_event_rfqs": orphaned,
        "per_rfq": [
            {
                "rfq_id": item["rfq_id"],
                "submission_pack_generated": item["submission_pack_generated"],
                "audit_integrity": item["audit_integrity"],
                "audit_event_counts": item["audit_event_counts"],
                "audit_events_missing": item["audit_events_missing"],
                "duplicate_audit_events": item["duplicate_audit_events"],
            }
            for item in results
        ],
    }

    _write_json(run_root / "simulation_manifest.json", manifest)
    _write_json(run_root / "simulation_results.json", results)
    _write_json(run_root / "simulation_metrics.json", metrics)
    _write_json(run_root / "simulation_audit.json", audit_summary)

    lane_report = calculate_lane_metrics(results)

    _write_json(
        run_root / "simulation_lane_metrics.json",
        lane_report,
    )
    
    return {
        "status": "ok",
        "run_id": run_id,
        "run_root": str(run_root),
        "manifest_path": str(run_root / "simulation_manifest.json"),
        "results_path": str(run_root / "simulation_results.json"),
        "metrics_path": str(run_root / "simulation_metrics.json"),
        "audit_path": str(run_root / "simulation_audit.json"),
        "metrics": metrics,
    }
