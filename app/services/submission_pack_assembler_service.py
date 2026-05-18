from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List


def _clean(value: Any) -> str:
    return str(value or "").replace("\xa0", " ").strip()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _existing_paths(paths: List[str]) -> List[str]:
    output: List[str] = []
    for p in paths:
        cleaned = _clean(p)
        if not cleaned:
            continue
        if Path(cleaned).exists():
            output.append(cleaned)
    return output


def build_submission_pack(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    metadata = _safe_dict(payload.get("metadata"))

    buyer_pdf = _clean(payload.get("rendered_buyer_pdf_path"))
    quote_pack_pdf = _clean(payload.get("quote_pack_pdf_path"))
    compliance_docs = _safe_list(metadata.get("compliance_document_paths"))
    extra_pack_docs = _safe_list(metadata.get("extra_submission_paths"))

    included_paths = _existing_paths(
        [quote_pack_pdf, buyer_pdf] + [str(x) for x in compliance_docs] + [str(x) for x in extra_pack_docs]
    )

    rfq_number = _clean(
        payload.get("rfq_number")
        or payload.get("reference_number")
        or metadata.get("buyer_rfq_number")
        or "RFQ"
    )
    safe_ref = "".join(ch if ch.isalnum() else "_" for ch in rfq_number).strip("_") or "RFQ"

    output_dir = Path(_clean(metadata.get("pdf_output_dir") or "runtime/generated_quotes"))
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / f"{safe_ref}_submission_pack_manifest.txt"

    manifest_lines = [
        f"Submission Pack Manifest",
        f"RFQ Number: {rfq_number}",
        f"Buyer Name: {_clean(payload.get('buyer_name') or metadata.get('buyer_name'))}",
        f"Document Title: {_clean(payload.get('title') or metadata.get('title'))}",
        f"Review Rows Held Back: {len(_safe_list(payload.get('review_rows')))}",
        "",
        "Included Files:",
    ]
    if included_paths:
        manifest_lines.extend(f"- {p}" for p in included_paths)
    else:
        manifest_lines.append("- None")

    manifest_path.write_text("\n".join(manifest_lines), encoding="utf-8")

    return {
        "submission_pack_assembler": {
            "included_file_count": len(included_paths),
            "included_files": included_paths,
            "review_rows_held_back": len(_safe_list(payload.get("review_rows"))),
            "submission_pack_manifest_path": str(manifest_path),
            "has_quote_pack_pdf": bool(quote_pack_pdf and Path(quote_pack_pdf).exists()),
            "has_buyer_schedule_pdf": bool(buyer_pdf and Path(buyer_pdf).exists()),
        },
        "submission_pack_manifest_path": str(manifest_path),
        "submission_pack_files": included_paths,
        "submission_pack_ready_count": len(included_paths),
    }


def attach_submission_pack_to_record(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    payload.update(build_submission_pack(payload))
    return payload


