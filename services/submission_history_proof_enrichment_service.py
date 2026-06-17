from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
SUBMISSION_HISTORY_FILE = RUNTIME_DIR / "submission_history" / "submission_history.json"
PROOF_DIR = RUNTIME_DIR / "submission_proofs"


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _read_json(path: Path, default: Any = None) -> Any:
    if default is None:
        default = []
    try:
        if not path.exists() or not path.is_file():
            return default
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return default
        return json.loads(text)
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _record_matches_proof(record: Dict[str, Any], metadata: Dict[str, Any]) -> bool:
    record_rfq = _safe_str(record.get("buyer_rfq_number")).lower()
    record_quote = _safe_str(record.get("quote_number")).lower()
    record_submitted = _safe_str(record.get("submitted_at"))

    meta_rfq = _safe_str(metadata.get("buyer_rfq_number")).lower()
    meta_quote = _safe_str(metadata.get("quote_number")).lower()
    meta_submitted = _safe_str(metadata.get("submitted_at"))

    if record_quote and meta_quote and record_quote == meta_quote:
        return True

    if record_rfq and meta_rfq and record_rfq == meta_rfq:
        if not record_submitted or not meta_submitted or record_submitted == meta_submitted:
            return True

    return False


def _find_matching_proof(record: Dict[str, Any]) -> Dict[str, Any]:
    # 1. Use already attached proof_result if present.
    proof_result = record.get("proof_result")
    if isinstance(proof_result, dict) and proof_result.get("proof_pdf_path"):
        return {
            "proof_pdf_path": proof_result.get("proof_pdf_path"),
            "proof_metadata_path": proof_result.get("proof_metadata_path", ""),
            "proof_generated": True,
            "proof_source": "record.proof_result",
        }

    # 2. Search proof metadata JSON files.
    if PROOF_DIR.exists():
        metadata_files = sorted(
            PROOF_DIR.rglob("*proof_of_submission.json"),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
            reverse=True,
        )

        for metadata_file in metadata_files:
            metadata = _read_json(metadata_file, default={})
            if not isinstance(metadata, dict):
                continue

            if _record_matches_proof(record, metadata):
                pdf_path = _safe_str(metadata.get("proof_pdf_path"))
                if pdf_path:
                    return {
                        "proof_pdf_path": pdf_path,
                        "proof_metadata_path": str(metadata_file),
                        "proof_generated": True,
                        "proof_source": "proof_metadata",
                    }

    # 3. Search PDF files by RFQ/quote hints.
    rfq = _safe_str(record.get("buyer_rfq_number")).lower()
    quote = _safe_str(record.get("quote_number")).lower()

    if PROOF_DIR.exists():
        pdfs = sorted(
            PROOF_DIR.rglob("*.pdf"),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
            reverse=True,
        )

        for pdf in pdfs:
            name = pdf.name.lower()
            parent = pdf.parent.name.lower()
            if quote and quote[:35].replace(" ", "-").replace(":", "-").lower() in name:
                return {
                    "proof_pdf_path": str(pdf),
                    "proof_metadata_path": "",
                    "proof_generated": True,
                    "proof_source": "proof_pdf_search_quote",
                }
            if rfq and rfq[:35].replace(" ", "-").replace(":", "-").lower() in (name + parent):
                return {
                    "proof_pdf_path": str(pdf),
                    "proof_metadata_path": "",
                    "proof_generated": True,
                    "proof_source": "proof_pdf_search_rfq",
                }

    return {
        "proof_pdf_path": "",
        "proof_metadata_path": "",
        "proof_generated": False,
        "proof_source": "none",
    }


def enrich_submission_history_with_proof_paths() -> Dict[str, Any]:
    history = _read_json(SUBMISSION_HISTORY_FILE, default=[])
    if not isinstance(history, list):
        history = []

    updated = 0
    missing = 0
    items: List[Dict[str, Any]] = []

    for record in history:
        if not isinstance(record, dict):
            continue

        proof = _find_matching_proof(record)

        previous_path = _safe_str(record.get("proof_pdf_path"))
        new_path = _safe_str(proof.get("proof_pdf_path"))

        if new_path:
            record["proof_pdf_path"] = new_path
            record["proof_url"] = "/" + new_path.lstrip("/")
            record["proof_metadata_path"] = proof.get("proof_metadata_path", "")
            record["proof_generated"] = True
            record["proof_source"] = proof.get("proof_source", "")
            if previous_path != new_path:
                updated += 1
        else:
            record.setdefault("proof_pdf_path", "")
            record.setdefault("proof_url", "")
            record["proof_generated"] = False
            missing += 1

        items.append(record)

    _write_json(SUBMISSION_HISTORY_FILE, history)

    return {
        "status": "ok",
        "history_file": str(SUBMISSION_HISTORY_FILE),
        "proof_dir": str(PROOF_DIR),
        "count": len(history),
        "updated": updated,
        "missing": missing,
        "items_with_proof": len([x for x in history if isinstance(x, dict) and x.get("proof_pdf_path")]),
    }


def get_submission_history_with_proofs(limit: int = 20) -> Dict[str, Any]:
    enrich_submission_history_with_proof_paths()

    history = _read_json(SUBMISSION_HISTORY_FILE, default=[])
    if not isinstance(history, list):
        history = []

    history = sorted(
        [x for x in history if isinstance(x, dict)],
        key=lambda x: _safe_str(x.get("submitted_at")),
        reverse=True,
    )

    items = history[: max(1, int(limit or 20))]

    return {
        "status": "ok",
        "source": str(SUBMISSION_HISTORY_FILE),
        "available": SUBMISSION_HISTORY_FILE.exists(),
        "count": len(items),
        "submitted": len([x for x in items if _safe_str(x.get("status")).lower() == "submitted"]),
        "failed": len([x for x in items if _safe_str(x.get("status")).lower() == "failed"]),
        "items_with_proof": len([x for x in items if x.get("proof_pdf_path")]),
        "items": items,
        "submissions": items,
        "recent": items,
    }
