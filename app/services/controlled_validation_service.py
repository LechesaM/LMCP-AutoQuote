from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services import quote_compilation_service
from app.services.immutable_submission_lock_service import get_submission_lock_status


RUNTIME_DIR = Path("runtime")
OUTPUT_ROOT = RUNTIME_DIR / "quote_compilation"
CONTROLLED_VALIDATION_DIR = RUNTIME_DIR / "controlled_validation"
CONTROLLED_VALIDATION_SET_FILE = CONTROLLED_VALIDATION_DIR / "controlled_validation_set.json"
CONTROLLED_VALIDATION_REPORT_FILE = CONTROLLED_VALIDATION_DIR / "controlled_validation_report.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _candidate_from_workspace(workspace: Path) -> Optional[Dict[str, Any]]:
    manifest = _read_json(workspace / "quote_pack_manifest.json")
    readiness_payload = _read_json(workspace / "submission_binder_readiness.json")
    checklist = _read_json(workspace / "returnables_checklist.json")
    pack_id = _safe_text(manifest.get("pack_id")) or workspace.name
    rfq_reference = _safe_text(manifest.get("rfq_reference")) or _safe_text(checklist.get("rfq_reference")) or pack_id
    if not rfq_reference:
        return None
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    primary_file = files[0] if files and isinstance(files[0], dict) else {}
    forms = checklist.get("sbd_forms") if isinstance(checklist.get("sbd_forms"), list) else []
    missing_items = checklist.get("missing_items") if isinstance(checklist.get("missing_items"), list) else []
    return {
        "pack_id": pack_id,
        "workspace": workspace.name,
        "workspace_path": str(workspace),
        "rfq_reference": rfq_reference,
        "title": _safe_text(manifest.get("title")),
        "boq_style": _safe_text(primary_file.get("type")) or "unknown",
        "readiness_score": int(
            (readiness_payload.get("readiness") or {}).get("submission_binder_score")
            or (manifest.get("readiness") or {}).get("quote_readiness_score")
            or 0
        ),
        "forms_count": len(forms),
        "missing_items": [_safe_text(item) for item in missing_items if _safe_text(item)],
    }


def _list_candidates() -> List[Dict[str, Any]]:
    if not OUTPUT_ROOT.exists():
        return []
    candidates: List[Dict[str, Any]] = []
    for workspace in sorted([path for path in OUTPUT_ROOT.iterdir() if path.is_dir()]):
        candidate = _candidate_from_workspace(workspace)
        if candidate:
            candidates.append(candidate)
    return candidates


def _select_diverse_candidates(candidates: List[Dict[str, Any]], minimum: int, limit: int) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in sorted(candidates, key=lambda value: (-int(value.get("readiness_score") or 0), value.get("pack_id") or "")):
        grouped[_safe_text(item.get("boq_style")) or "unknown"].append(item)

    selected: List[Dict[str, Any]] = []
    seen_refs = set()
    for group in grouped.values():
        for item in group:
            ref = _safe_text(item.get("rfq_reference"))
            if ref and ref not in seen_refs:
                selected.append(item)
                seen_refs.add(ref)
                break

    for item in sorted(candidates, key=lambda value: (-int(value.get("readiness_score") or 0), value.get("pack_id") or "")):
        ref = _safe_text(item.get("rfq_reference"))
        if not ref or ref in seen_refs:
            continue
        selected.append(item)
        seen_refs.add(ref)
        if len(selected) >= max(minimum, min(limit, len(candidates))):
            break

    return selected[: max(1, min(limit, len(selected)))]


def select_controlled_validation_set(limit: int = 10, minimum: int = 5) -> Dict[str, Any]:
    candidates = _list_candidates()
    safe_limit = max(1, int(limit or 10))
    safe_minimum = max(1, int(minimum or 5))
    selected = _select_diverse_candidates(candidates, safe_minimum, safe_limit)
    payload = {
        "status": "ok" if len(selected) >= safe_minimum else "insufficient_candidates",
        "selected_count": len(selected),
        "minimum_required": safe_minimum,
        "limit": safe_limit,
        "selected": selected,
        "generated_at": _now_iso(),
    }
    _write_json(CONTROLLED_VALIDATION_SET_FILE, payload)
    return payload


def _evaluate_selected_pack(item: Dict[str, Any]) -> Dict[str, Any]:
    pack_id = _safe_text(item.get("pack_id"))
    rfq_reference = _safe_text(item.get("rfq_reference")) or None
    gate = quote_compilation_service.get_submission_binder_gate(pack_id, rfq_reference=rfq_reference)
    checklist = quote_compilation_service.get_submission_binder_gate_checklist(pack_id, rfq_reference=rfq_reference, include_text=False)
    audit_log = quote_compilation_service.get_submission_binder_gate_audit_log(pack_id, rfq_reference=rfq_reference)
    clean = bool(
        gate.get("can_prepare_submission")
        and gate.get("manual_completion_allowed")
        and not (gate.get("blockers") or [])
        and not (gate.get("missing_returnables") or [])
        and _safe_text(audit_log.get("readiness_status")) in {"manual_completion_recorded", "ready_for_manual_submission"}
    )
    return {
        **item,
        "gate": gate,
        "checklist": checklist,
        "audit_log": audit_log,
        "clean": clean,
    }


def build_controlled_validation_report(limit: int = 10, minimum: int = 5) -> Dict[str, Any]:
    selected_payload = select_controlled_validation_set(limit=limit, minimum=minimum)
    selected_items = [_evaluate_selected_pack(item) for item in selected_payload.get("selected") or [] if isinstance(item, dict)]
    fully_clean_packs = sum(1 for item in selected_items if item.get("clean"))
    selected_count = len(selected_items)
    confidence_score = int(round((fully_clean_packs / selected_count) * 100)) if selected_count else 0
    lock_status = get_submission_lock_status(limit=50)
    lock_valid = bool((lock_status.get("verification") or {}).get("valid")) and bool((lock_status.get("summary") or {}).get("valid"))
    status = "ready_for_v49" if selected_count >= max(1, int(minimum or 5)) and fully_clean_packs == selected_count and lock_valid else "hardening_required"
    payload = {
        "status": status,
        "generated_at": _now_iso(),
        "summary": {
            "selected_packs": selected_count,
            "fully_clean_packs": fully_clean_packs,
            "lock_chain_valid": lock_valid,
        },
        "confidence_score": confidence_score,
        "selected": selected_items,
        "immutable_submission_lock": lock_status,
        "production_confidence_matrix": [
            {"metric": "fully_clean_packs", "value": fully_clean_packs, "target": selected_count},
            {"metric": "confidence_score", "value": confidence_score, "target": 100},
            {"metric": "immutable_submission_lock_valid", "value": 1 if lock_valid else 0, "target": 1},
        ],
    }
    _write_json(CONTROLLED_VALIDATION_REPORT_FILE, payload)
    return payload
