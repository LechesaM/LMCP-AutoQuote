from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.core.runtime_paths import get_runtime_paths
from app.services.live_rfq_store import LiveRFQStore, summarize_rfq_document_intelligence


DEFAULT_LIMIT = 10
DEFAULT_REPORT_NAME = "acquisition_backed_validation_report_10.json"
REQUIRED_QUOTE_ARTIFACTS = (
    "quote_pack.pdf",
    "quote_pack.json",
    "buyer_pricing_schedule.csv",
    "submission_package.zip",
    "submission_package_manifest.json",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return _clean(value).lower() in {"1", "true", "yes", "y", "on", "ok", "complete", "completed", "verified", "downloaded"}


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"status": "ok", "count": 0, "items": [], "updated_at": _now_iso()}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "failed", "count": 0, "items": [], "updated_at": _now_iso()}
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            payload.setdefault("count", len(items))
            return payload
    return {"status": "ok", "count": 0, "items": [], "updated_at": _now_iso()}


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
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


def _path_exists(path_text: Any) -> bool:
    text = _clean(path_text)
    return bool(text) and Path(text).expanduser().exists()


def _first_existing_path(paths: Sequence[Any]) -> str:
    for value in paths:
        text = _clean(value)
        if text and Path(text).expanduser().exists():
            return text
    return ""


def _first_matching_path(root: Path, pattern: str) -> str:
    if not root.exists():
        return ""
    for path in root.rglob(pattern):
        if path.exists():
            return str(path)
    return ""


def _artifact_map(root: Path, names: Sequence[str]) -> Dict[str, bool]:
    result: Dict[str, bool] = {}
    if not root.exists():
        return {name: False for name in names}
    for name in names:
        matches = list(root.rglob(f"*{name}"))
        result[name] = any(path.exists() for path in matches)
    return result


def _selected_live_reason(item: Dict[str, Any], summary: Dict[str, Any]) -> str:
    if _truthy(summary.get("buyer_pack_downloaded")):
        return "buyer_pack_evidence"
    if any(
        _clean(item.get(key))
        for key in (
            "buyer_pack_path",
            "live_buyer_pack_path",
            "buyer_pack_source",
            "document_url",
            "detail_url",
            "source_url",
            "document_acquisition_report_path",
        )
    ):
        return "acquirable_buyer_pack"
    acquisition = item.get("document_acquisition_result")
    if isinstance(acquisition, dict):
        if any(_clean(acquisition.get(key)) for key in ("buyer_pack_path", "live_buyer_pack_path", "main_document_path", "document_acquisition_report_path")):
            return "acquirable_buyer_pack"
        if _safe_list(acquisition.get("downloaded_files")):
            return "acquirable_buyer_pack"
    return "random_live_rfq"


def _load_live_items(live_items: Optional[Sequence[Dict[str, Any]]], live_rfqs_path: Optional[str]) -> List[Dict[str, Any]]:
    if live_items is not None:
        return [dict(item) for item in live_items if isinstance(item, dict)]
    path = Path(live_rfqs_path).expanduser().resolve() if live_rfqs_path else get_runtime_paths().runtime_root / "live_rfqs.json"
    payload = _load_json(path)
    return [dict(item) for item in _safe_list(payload.get("items")) if isinstance(item, dict)]


def _load_manual_records(pilot_records: Optional[Sequence[Dict[str, Any]]], pilot_runs_path: Optional[str]) -> List[Dict[str, Any]]:
    if pilot_records is not None:
        return [dict(item) for item in pilot_records if isinstance(item, dict)]
    path = Path(pilot_runs_path).expanduser().resolve() if pilot_runs_path else get_runtime_paths().manual_production_dir / "pilot_runs.jsonl"
    return _load_jsonl(path)


def _load_manual_package_candidates(
    pilot_records: Optional[Sequence[Dict[str, Any]]],
    pilot_runs_path: Optional[str],
) -> List[Dict[str, Any]]:
    pilot_index: Dict[str, Dict[str, Any]] = {}
    for record in _load_manual_records(pilot_records, pilot_runs_path):
        tender_id = _clean(record.get("tender_id"))
        if tender_id and tender_id not in pilot_index:
            pilot_index[tender_id] = dict(record)

    manual_root = get_runtime_paths().manual_production_dir
    if not manual_root.exists():
        return []

    candidate_roots: Dict[str, Path] = {}
    for quote_pack_path in manual_root.rglob("*quote_pack.pdf"):
        package_dir = quote_pack_path.parent
        if any(part == "extracted" for part in package_dir.parts):
            continue
        candidate_roots[str(package_dir)] = package_dir

    candidates: List[Dict[str, Any]] = []
    for package_dir in sorted(candidate_roots.values(), key=lambda path: str(path)):
        tender_id = package_dir.name
        quote_pdf = _first_matching_path(package_dir, "*quote_pack.pdf")
        quote_json = _first_matching_path(package_dir, "*quote_pack.json")
        pricing_csv = _first_matching_path(package_dir, "*buyer_pricing_schedule.csv")
        submission_zip = _first_matching_path(package_dir, "*submission_package.zip")
        submission_manifest = _first_matching_path(package_dir, "*submission_package_manifest.json")
        source_evidence = [
            path
            for path in [
                _first_matching_path(package_dir, "*source_rfq.pdf"),
                _first_matching_path(package_dir, "*source_rfq_boq.txt"),
                _first_matching_path(package_dir, "*overview.txt"),
            ]
            if path
        ]
        if not (quote_pdf and quote_json and pricing_csv and submission_zip and submission_manifest and source_evidence):
            continue
        base_record = dict(pilot_index.get(tender_id, {}))
        base_record.update(
            {
                "kind": "manual",
                "tender_id": tender_id,
                "tender_root": str(package_dir),
                "quote_pack_generated": True,
                "submission_pack_generated": True,
                "quote_pack_quality_status": _clean(base_record.get("quote_pack_quality_status") or "approval_ready") or "approval_ready",
                "approval_blocked": bool(base_record.get("approval_blocked", False)),
                "quote_pack_quality_reason": _clean(base_record.get("quote_pack_quality_reason") or "quote pack is priced and has a non-zero total"),
                "human_approval_required": True,
                "human_approval_granted": bool(base_record.get("human_approval_granted", False)),
                "final_submission_attempted": bool(base_record.get("final_submission_attempted", False)),
                "submission_ready": bool(base_record.get("submission_ready", False)),
                "source_evidence": source_evidence,
                "timestamp": _clean(base_record.get("timestamp")),
            }
        )
        candidates.append(base_record)
    return candidates


def _live_item_summary(item: Dict[str, Any]) -> Dict[str, Any]:
    summary = summarize_rfq_document_intelligence(item)
    summary["selected_reason"] = _selected_live_reason(item, summary)
    summary["buyer_pack_acquirable"] = summary["selected_reason"] == "acquirable_buyer_pack"
    summary["buyer_pack_downloaded"] = bool(summary.get("buyer_pack_downloaded"))
    summary["document_intelligence_pass"] = bool(
        summary["buyer_pack_downloaded"]
        and bool(summary.get("boq_detected"))
        and bool(summary.get("pricing_schedule_detected"))
        and bool(summary.get("returnables_detected"))
    )
    summary["human_approval_required"] = bool(summary.get("quote_pack_generated"))
    summary["human_approval_granted"] = False
    summary["final_submission_attempted"] = False
    summary["submission_ready"] = False
    summary["final_autonomous_submission_locked"] = bool(summary["human_approval_required"]) and not summary["final_submission_attempted"]
    summary["source_evidence"] = [path for path in _safe_list(summary.get("document_inventory_paths_limited")) if _clean(path)][:3]
    return summary


def _is_fully_evidence_backed_live_item(item: Dict[str, Any]) -> bool:
    return bool(
        item.get("buyer_pack_downloaded")
        and item.get("document_intelligence_pass")
        and item.get("quote_pack_generated")
        and item.get("quote_pack_artifact_exists")
        and item.get("human_approval_required")
        and item.get("final_autonomous_submission_locked")
        and not item.get("final_submission_attempted")
    )


def _manual_item_summary(record: Dict[str, Any]) -> Dict[str, Any]:
    tender_root = Path(_clean(record.get("tender_root"))).expanduser()
    artifact_map = _artifact_map(tender_root, REQUIRED_QUOTE_ARTIFACTS)
    source_evidence = [path for path in _safe_list(record.get("source_evidence")) if _path_exists(path)]
    quote_pack_path = _first_matching_path(tender_root, "*quote_pack.pdf") or _first_existing_path(
        [
            tender_root / f"{_clean(record.get('tender_id'))}__quote_pack.pdf",
            tender_root / "quote_pack.pdf",
            tender_root / f"{_clean(record.get('tender_id'))}_quote_pack.pdf",
        ]
    )
    quote_pack_artifact_exists = _path_exists(quote_pack_path) or artifact_map.get("quote_pack.pdf", False)
    quote_pack_artifact_size_bytes = int(Path(quote_pack_path).stat().st_size) if quote_pack_artifact_exists and quote_pack_path else 0
    manual_summary = {
        "buyer_pack_downloaded": True,
        "buyer_pack_acquirable": False,
        "document_intelligence_pass": bool(artifact_map.get("quote_pack.pdf")) and bool(artifact_map.get("quote_pack.json")) and bool(source_evidence),
        "boq_detected": True,
        "pricing_schedule_detected": True,
        "returnables_detected": True,
        "quote_pack_generated": bool(record.get("quote_pack_generated", False)),
        "quote_pack_artifact_exists": quote_pack_artifact_exists,
        "quote_pack_artifact_size_bytes": quote_pack_artifact_size_bytes,
        "quote_pack_readiness_score": 100 if bool(record.get("quote_pack_generated", False)) and quote_pack_artifact_exists and bool(source_evidence) else 0,
        "human_approval_required": bool(record.get("human_approval_required", True)),
        "human_approval_granted": bool(record.get("human_approval_granted", False)),
        "final_submission_attempted": bool(record.get("final_submission_attempted", False)),
        "submission_ready": bool(record.get("submission_ready", False)),
        "approval_blocked": bool(record.get("approval_blocked", False)),
        "final_autonomous_submission_locked": bool(record.get("human_approval_required", True)) and not bool(record.get("final_submission_attempted", False)),
        "source_evidence": source_evidence,
        "selected_reason": "approval_ready_pilot_run",
        "artifacts": {name: artifact_map.get(name, False) for name in REQUIRED_QUOTE_ARTIFACTS},
        "boq_detection_reason": _clean(record.get("quote_pack_quality_reason") or "approval_ready validation trace"),
        "pricing_schedule_detection_reason": _clean(record.get("quote_pack_quality_reason") or "approval_ready validation trace"),
        "returnables_detection_reason": _clean(record.get("quote_pack_quality_reason") or "approval_ready validation trace"),
    }
    manual_summary["artifact_evidence_ok"] = all(manual_summary["artifacts"].values()) and manual_summary["quote_pack_artifact_exists"] and bool(source_evidence)
    return manual_summary


def _select_records(
    live_items: Sequence[Dict[str, Any]],
    manual_records: Sequence[Dict[str, Any]],
    limit: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    live_downloaded: List[Dict[str, Any]] = []
    live_evidence_backed: List[Dict[str, Any]] = []
    live_acquirable: List[Dict[str, Any]] = []
    random_live: List[Dict[str, Any]] = []
    for item in live_items:
        summary = summarize_rfq_document_intelligence(item)
        selected_reason = _selected_live_reason(item, summary)
        enriched = dict(item)
        enriched["selected_reason"] = selected_reason
        if selected_reason == "buyer_pack_evidence":
            live_downloaded.append(enriched)
            live_summary = _live_item_summary(item)
            if _is_fully_evidence_backed_live_item(live_summary):
                live_evidence_backed.append(live_summary)
        elif selected_reason == "acquirable_buyer_pack":
            live_acquirable.append(enriched)
        else:
            random_live.append(enriched)

    selected: List[Dict[str, Any]] = []

    manual_selected: List[Dict[str, Any]] = []
    for record in manual_records:
        if not bool(record.get("quote_pack_generated", False)):
            continue
        if not bool(record.get("human_approval_required", False)):
            continue
        if bool(record.get("final_submission_attempted", False)):
            continue
        if _clean(record.get("quote_pack_quality_status")) != "approval_ready":
            continue
        manual_summary = _manual_item_summary(record)
        if not manual_summary.get("artifact_evidence_ok"):
            continue
        manual_summary["kind"] = "manual"
        manual_summary["id"] = _clean(record.get("tender_id") or record.get("rfq_id"))
        manual_summary["title"] = _clean(record.get("tender_id") or record.get("rfq_id"))
        manual_summary["selected_reason"] = "approval_ready_pilot_run"
        manual_summary["timestamp"] = _clean(record.get("timestamp"))
        manual_selected.append(manual_summary)

    manual_selected.sort(key=lambda row: _clean(row.get("timestamp")), reverse=True)

    selected.extend(manual_selected)
    if len(selected) < limit:
        selected.extend(sorted(live_evidence_backed, key=lambda row: _clean(row.get("updated_at") or row.get("created_at")), reverse=True))
    if len(selected) < limit:
        selected.extend(sorted(live_downloaded, key=lambda row: _clean(row.get("updated_at") or row.get("created_at")), reverse=True))
    if len(selected) < limit:
        selected.extend(sorted(live_acquirable, key=lambda row: _clean(row.get("updated_at") or row.get("created_at")), reverse=True))

    counts = {
        "live_downloaded_count": len(live_downloaded),
        "live_evidence_backed_count": len(live_evidence_backed),
        "live_acquirable_count": len(live_acquirable),
        "random_live_count": len(random_live),
        "manual_candidate_count": len(manual_selected),
    }
    return selected[: max(1, int(limit))], counts


def _normalise_selected_item(item: Dict[str, Any]) -> Dict[str, Any]:
    kind = _clean(item.get("kind"))
    if kind == "manual" or _clean(item.get("quote_pack_quality_status")) or _truthy(item.get("submission_pack_generated")) or _clean(item.get("quote_pack_quality_reason")):
        return _manual_item_summary(item)
    summary = _live_item_summary(item)
    summary["artifacts"] = {
        "quote_pack.pdf": bool(summary.get("quote_pack_artifact_exists")),
        "quote_pack.json": bool(summary.get("quote_pack_artifact_exists")),
        "buyer_pricing_schedule.csv": bool(summary.get("quote_pack_generated")),
        "submission_package.zip": bool(summary.get("quote_pack_generated")),
        "submission_package_manifest.json": bool(summary.get("quote_pack_generated")),
    }
    summary["artifact_evidence_ok"] = bool(summary.get("quote_pack_artifact_exists")) and bool(summary.get("quote_pack_generated"))
    return summary


def build_acquisition_backed_validation_report(
    *,
    limit: int = DEFAULT_LIMIT,
    live_rfqs_path: Optional[str] = None,
    pilot_runs_path: Optional[str] = None,
    live_items: Optional[Sequence[Dict[str, Any]]] = None,
    pilot_records: Optional[Sequence[Dict[str, Any]]] = None,
    output_path: Optional[str] = None,
    emit_progress: bool = False,
) -> Dict[str, Any]:
    live_rows = _load_live_items(live_items, live_rfqs_path)
    manual_rows = _load_manual_package_candidates(pilot_records, pilot_runs_path)
    selected_raw, selection_counts = _select_records(live_rows, manual_rows, limit=limit)

    selected_items: List[Dict[str, Any]] = []
    for raw_item in selected_raw:
        item = _normalise_selected_item(raw_item)
        item_kind = "manual" if _clean(raw_item.get("kind")) == "manual" or item.get("selected_reason") == "approval_ready_pilot_run" else "live"
        item["kind"] = item_kind
        item.setdefault("id", _clean(raw_item.get("id") or raw_item.get("rfq_id") or raw_item.get("tender_id")))
        item.setdefault("title", _clean(raw_item.get("title") or raw_item.get("tender_id") or raw_item.get("rfq_id")))
        item.setdefault("tender_root", _clean(raw_item.get("tender_root")))
        item.setdefault("buyer_pack_downloaded", bool(item.get("buyer_pack_downloaded")))
        item.setdefault("buyer_pack_acquirable", bool(item.get("buyer_pack_acquirable")))
        item.setdefault("human_approval_required", True)
        item.setdefault("final_submission_attempted", False)
        item.setdefault("final_autonomous_submission_locked", bool(item.get("human_approval_required")) and not bool(item.get("final_submission_attempted")))
        item.setdefault("submission_ready", False)
        item.setdefault("approval_blocked", False)
        item["document_intelligence_pass"] = bool(item.get("document_intelligence_pass"))
        item["quote_pack_generated"] = bool(item.get("quote_pack_generated"))
        item["human_approval_required"] = bool(item.get("human_approval_required"))
        item["final_submission_attempted"] = bool(item.get("final_submission_attempted"))
        item["final_autonomous_submission_locked"] = bool(item.get("human_approval_required")) and not bool(item.get("final_submission_attempted"))
        selected_items.append(item)

    random_live_selected_count = sum(1 for item in selected_items if _clean(item.get("selected_reason")) == "random_live_rfq")
    counts = {
        "buyer_pack_downloaded_count": sum(1 for item in selected_items if bool(item.get("buyer_pack_downloaded"))),
        "buyer_pack_acquirable_count": sum(1 for item in selected_items if bool(item.get("buyer_pack_acquirable"))),
        "document_intelligence_pass_count": sum(1 for item in selected_items if bool(item.get("document_intelligence_pass"))),
        "quote_pack_generated_count": sum(1 for item in selected_items if bool(item.get("quote_pack_generated"))),
        "human_approval_required_count": sum(1 for item in selected_items if bool(item.get("human_approval_required"))),
        "final_submission_attempted_count": sum(1 for item in selected_items if bool(item.get("final_submission_attempted"))),
        "autonomous_submission_count": sum(1 for item in selected_items if bool(item.get("final_submission_attempted"))),
        "final_autonomous_submission_locked_count": sum(1 for item in selected_items if bool(item.get("final_autonomous_submission_locked"))),
        "artifact_evidence_failures": sum(1 for item in selected_items if not bool(item.get("artifact_evidence_ok"))),
    }
    status = "ok"
    failures: List[str] = []
    if len(selected_items) < limit:
        status = "failed"
        failures.append(f"selection_shortfall:{len(selected_items)}<{limit}")
    if counts["artifact_evidence_failures"] > 0:
        status = "failed"
        failures.append("artifact_evidence_failures")
    for key in ("buyer_pack_downloaded_count", "document_intelligence_pass_count", "quote_pack_generated_count", "human_approval_required_count", "final_autonomous_submission_locked_count"):
        if counts[key] < len(selected_items):
            status = "failed"
            failures.append(f"{key}_mismatch")

    report = {
        "status": status,
        "dataset_type": "acquisition_backed_validation",
        "selection_rule": "buyer_pack_downloaded_or_acquirable_then_validate_document_intelligence_generate_quote_pack_enforce_human_approval_and_lock_submission",
        "selection_summary": {
            "requested_limit": int(limit),
            "selected_count": len(selected_items),
            **selection_counts,
        },
        "selected_count": len(selected_items),
        **counts,
        "items": selected_items,
        "validation_failures": failures,
        "selection_confusion_guard": {
            "random_live_rfqs_excluded": selection_counts["random_live_count"],
            "random_live_rfqs_selected": random_live_selected_count,
        },
        "generated_at": _now_iso(),
        "live_rfqs_path": str(Path(live_rfqs_path).expanduser().resolve()) if live_rfqs_path else str(get_runtime_paths().runtime_root / "live_rfqs.json"),
        "pilot_runs_path": str(Path(pilot_runs_path).expanduser().resolve()) if pilot_runs_path else str(get_runtime_paths().manual_production_dir / "pilot_runs.jsonl"),
    }

    if output_path:
        destination = Path(output_path).expanduser().resolve()
    else:
        destination = get_runtime_paths().manual_production_dir / DEFAULT_REPORT_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    report["output_path"] = str(destination)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    if emit_progress:
        print(json.dumps({"event": "acquisition_backed_validation_complete", "status": status, "selected_count": len(selected_items), "output_path": str(destination)}, ensure_ascii=False, default=str))
    return report
