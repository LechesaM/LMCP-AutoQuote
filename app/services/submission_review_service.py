from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from app.services import manual_approval_service
from app.persistence import db as persistence_db


RUNTIME_DIR = Path("runtime")
MANUAL_PRODUCTION_DIR = RUNTIME_DIR / "manual_production"
MANUAL_PRODUCTION_DIR.mkdir(parents=True, exist_ok=True)
SUBMISSION_REVIEW_LOG_FILE = MANUAL_PRODUCTION_DIR / "submission_reviews.jsonl"

_LOCK = Lock()

SUPPORTED_RFQ_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".zip", ".txt"}


def _resolve_runtime_path(default_path: Path, runtime_dir: Optional[str] = None) -> Path:
    if not runtime_dir:
        return default_path
    runtime_root = Path(runtime_dir).expanduser().resolve()
    try:
        relative = default_path.relative_to(RUNTIME_DIR)
    except Exception:
        return default_path
    return runtime_root / relative


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _slug_variants(value: str) -> List[str]:
    text = _clean(value)
    if not text:
        return []
    variants = [text]
    normalized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text).strip("._")
    if normalized and normalized not in variants:
        variants.append(normalized)
    underscored = normalized.replace("-", "_") if normalized else ""
    if underscored and underscored not in variants:
        variants.append(underscored)
    hyphenated = normalized.replace("_", "-") if normalized else ""
    if hyphenated and hyphenated not in variants:
        variants.append(hyphenated)
    return variants


def append_submission_review(record: Dict[str, Any], runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    item = dict(record or {})
    item.setdefault("timestamp", _now_iso())
    review_log = _resolve_runtime_path(SUBMISSION_REVIEW_LOG_FILE, runtime_dir)
    review_log.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(item, ensure_ascii=False, default=str)
    with _LOCK:
        with review_log.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    try:
        persistence_db.insert_json_record("submission_review_entities", item)
    except Exception:
        pass
    return item


def list_recent_submission_reviews(limit: int = 20, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    review_log = _resolve_runtime_path(SUBMISSION_REVIEW_LOG_FILE, runtime_dir)
    records: List[Dict[str, Any]] = []
    if review_log.exists():
        try:
            for line in review_log.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                if isinstance(payload, dict):
                    records.append(payload)
        except Exception:
            records = []
    recent = list(reversed(records[-max(1, int(limit or 20)) :]))
    return {
        "status": "ok",
        "items": recent,
        "total": len(records),
        "log_file": str(review_log),
        "updated_at": _now_iso(),
    }


def find_latest_submission_review(tender_id: str, tender_root: str, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    records = _read_jsonl(_resolve_runtime_path(SUBMISSION_REVIEW_LOG_FILE, runtime_dir))
    for record in reversed(records):
        if not isinstance(record, dict):
            continue
        if _clean(record.get("tender_id")) == _clean(tender_id) and _clean(record.get("tender_root")) == _clean(tender_root):
            return record
    return {}


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


def _match_tender(record: Dict[str, Any], tender_id: str, tender_root: str) -> bool:
    return _clean(record.get("tender_id")) == _clean(tender_id) and _clean(record.get("tender_root")) == _clean(tender_root)


def find_latest_approval(tender_id: str, tender_root: str, pricing_file: str = "", runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    records = _read_jsonl(_resolve_runtime_path(manual_approval_service.APPROVAL_LOG_FILE, runtime_dir))
    for record in reversed(records):
        if not isinstance(record, dict):
            continue
        if not _match_tender(record, tender_id, tender_root):
            continue
        if pricing_file and _clean(record.get("pricing_file")) and _clean(record.get("pricing_file")) != _clean(pricing_file):
            continue
        return record
    return {}


def _artifact_exists(paths: List[Path]) -> Optional[Path]:
    for path in paths:
        if path.exists():
            return path
    return None


def _quote_pack_candidates(tender_id: str, tender_root: str) -> List[Path]:
    root_path = Path(tender_root).expanduser()
    candidates: List[Path] = []
    for slug in _slug_variants(tender_id):
        candidates.append(root_path / f"{slug}__quote_pack.pdf")
        candidates.append(root_path / f"{slug}__quote_pack.json")
    runtime_root = RUNTIME_DIR
    for slug in _slug_variants(tender_id):
        candidates.extend(runtime_root.rglob(f"{slug}__quote_pack.pdf"))
        candidates.extend(runtime_root.rglob(f"{slug}__quote_pack.json"))
    return candidates


def _submission_pack_candidates(tender_id: str, tender_root: str) -> List[Path]:
    root_path = Path(tender_root).expanduser()
    candidates: List[Path] = []
    for slug in _slug_variants(tender_id):
        candidates.append(root_path / f"{slug}_submission_pack_manifest.txt")
    runtime_root = RUNTIME_DIR
    for slug in _slug_variants(tender_id):
        candidates.extend(runtime_root.rglob(f"{slug}_submission_pack_manifest.txt"))
    return candidates


def _source_rfq_present(tender_root: str) -> bool:
    root_path = Path(tender_root).expanduser()
    if not root_path.exists() or not root_path.is_dir():
        return False
    for path in root_path.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_RFQ_EXTENSIONS:
            return True
    return False


def build_submission_review_record(
    *,
    tender_id: str,
    tender_root: str,
    pricing_file: str = "",
    operator_name: str = "",
    runtime_dir: Optional[str] = None,
) -> Dict[str, Any]:
    approval = find_latest_approval(tender_id, tender_root, pricing_file=pricing_file, runtime_dir=runtime_dir)
    quote_pack_path = _artifact_exists(_quote_pack_candidates(tender_id, tender_root))
    submission_pack_path = _artifact_exists(_submission_pack_candidates(tender_id, tender_root))
    source_rfq_present = _source_rfq_present(tender_root)
    approval_present = bool(approval)
    final_submission_attempted = bool(approval.get("final_submission_attempted", False)) if approval_present else False
    submission_ready = bool(approval.get("submission_ready", False)) if approval_present else False

    blockers: List[str] = []
    if not approval_present:
        blockers.append("manual approval record missing")
    if not submission_ready:
        blockers.append("submission_ready must be true")
    if final_submission_attempted:
        blockers.append("final_submission_attempted must be false")
    if not quote_pack_path:
        blockers.append("quote pack missing")
    if not submission_pack_path:
        blockers.append("submission pack missing")
    if not source_rfq_present:
        blockers.append("source RFQ missing")

    review_ready = not blockers
    checklist = {
        "quote_pack_present": bool(quote_pack_path),
        "submission_pack_present": bool(submission_pack_path),
        "pricing_file_present": bool(_clean(approval.get("pricing_file")) and Path(_clean(approval.get("pricing_file"))).exists()) if approval_present else False,
        "source_rfq_present": source_rfq_present,
        "approval_record_present": approval_present,
        "final_submission_still_false": not final_submission_attempted,
    }
    return {
        "tender_id": _clean(tender_id),
        "tender_root": _clean(tender_root),
        "pricing_file": _clean(pricing_file),
        "operator_name": _clean(operator_name),
        "submission_review_ready": review_ready,
        "review_blockers": blockers,
        "quote_pack_present": checklist["quote_pack_present"],
        "submission_pack_present": checklist["submission_pack_present"],
        "pricing_file_present": checklist["pricing_file_present"],
        "source_rfq_present": checklist["source_rfq_present"],
        "approval_record_present": checklist["approval_record_present"],
        "final_submission_still_false": checklist["final_submission_still_false"],
        "submission_ready": submission_ready,
        "final_submission_attempted": final_submission_attempted,
        "approval_record": approval,
        "quote_pack_path": str(quote_pack_path) if quote_pack_path else "",
        "submission_pack_path": str(submission_pack_path) if submission_pack_path else "",
        "status": "review_ready" if review_ready else "refused",
        "timestamp": _now_iso(),
    }
