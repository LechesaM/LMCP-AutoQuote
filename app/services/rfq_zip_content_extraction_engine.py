from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json
import re
import shutil
import zipfile


ENGINE_VERSION = "RFQ_ZIP_CONTENT_EXTRACTION_ENGINE_V1"

RUNTIME_DIR = Path("runtime/rfq_zip_content_extraction")
EXTRACTED_DIR = RUNTIME_DIR / "extracted"
REPORT_DIR = RUNTIME_DIR / "reports"

MAX_ZIP_MEMBERS = 300
MAX_SINGLE_FILE_BYTES = 100 * 1024 * 1024

REJECT_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".mp3", ".mov", ".avi",
}

SUPPORTED_DOC_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt",
}

MAIN_TERMS = [
    "1. main",
    "1 main",
    "main.docx",
    "main document",
    "bid document",
    "tender document",
    "rfq document",
    "request for quotation",
    "request for proposal",
]

BOQ_TERMS = [
    "boq",
    "bill of quantities",
    "pricing schedule",
    "price schedule",
    "schedule of prices",
    "quotation schedule",
    "pricing",
]

PRICING_TERMS = [
    "pricing schedule",
    "price schedule",
    "schedule of prices",
    "quotation schedule",
    "pricing",
]

SBD_TERMS = [
    "sbd",
    "sbd forms",
    "standard bidding document",
    "declaration of interest",
    "preference points",
]

SPEC_TERMS = [
    "specification",
    "specifications",
    "scope of work",
    "terms of reference",
    "tor",
    "technical specification",
    "technical",
]

RETURNABLE_TERMS = [
    "returnable",
    "returnables",
    "returnable documents",
    "mandatory documents",
    "compulsory documents",
]

TERMS_TERMS = [
    "terms and conditions",
    "conditions of contract",
    "contract rev",
    "general conditions",
    "gcc",
]

SHEQ_TERMS = [
    "sheq",
    "safety",
    "health",
    "environmental",
    "alcohol",
    "drug",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any) -> str:
    try:
        if value is None:
            return ""
        return str(value).strip()
    except Exception:
        return ""


def _safe_lower(value: Any) -> str:
    return _safe_str(value).lower()


def _slug(value: Any, limit: int = 100) -> str:
    text = _safe_str(value)
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
    return (text[:limit].strip("-") or "rfq-zip")


def _ensure_dirs() -> None:
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _is_safe_zip_member(name: str) -> bool:
    name = _safe_str(name)
    if not name:
        return False

    normalised = name.replace("\\", "/")
    parts = [p for p in normalised.split("/") if p]

    if not parts:
        return False

    if any(p in {"..", "."} for p in parts):
        return False

    if normalised.startswith("/") or re.match(r"^[A-Za-z]:", normalised):
        return False

    if "__MACOSX" in parts:
        return False

    filename = parts[-1]
    if filename == ".DS_Store" or filename.startswith("._"):
        return False

    ext = Path(filename).suffix.lower()
    if ext in REJECT_EXTENSIONS:
        return False

    return True


def _clean_member_name(name: str) -> Path:
    name = _safe_str(name).replace("\\", "/")
    parts = [p for p in name.split("/") if p and p not in {".", ".."}]
    cleaned_parts = []
    for part in parts:
        part = re.sub(r"[^A-Za-z0-9._ ()&,+\-]", "-", part).strip(" .")
        if part:
            cleaned_parts.append(part)
    return Path(*cleaned_parts) if cleaned_parts else Path("file")


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for i in range(1, 1000):
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate

    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:8]
    return parent / f"{stem}_{digest}{suffix}"


def _locate_zip_files(acquisition_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(acquisition_result, dict):
        return []

    candidates: List[Dict[str, Any]] = []

    for key in ("downloaded_files", "prioritized_documents"):
        value = acquisition_result.get(key)
        if isinstance(value, list):
            candidates.extend([x for x in value if isinstance(x, dict)])

    best = acquisition_result.get("best_package_file")
    if isinstance(best, dict):
        candidates.append(best)

    # Some acquisition results store the downloaded best package only in
    # downloaded_files, while best_package_file is the pre-download candidate.
    zip_files: List[Dict[str, Any]] = []
    seen = set()

    for entry in candidates:
        raw_path = _safe_str(entry.get("path"))
        path = Path(raw_path) if raw_path else None
        ext = _safe_lower(entry.get("extension") or (path.suffix if path else ""))
        url = _safe_str(entry.get("url"))

        if ext != ".zip" and not (path and str(path).lower().endswith(".zip")) and not url.lower().endswith(".zip"):
            continue

        # best_package_file is often a pre-download candidate and may not have a
        # local path. Never treat empty path as current directory. Only extract
        # real downloaded ZIP files.
        if path is None or not path.exists() or not path.is_file():
            continue

        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)

        zip_files.append(entry)

    return zip_files


def _score_file(path: Path) -> Dict[str, Any]:
    name = _safe_lower(path.name)
    full = _safe_lower(str(path))
    blob = f"{name} {full}"

    score = 0.0
    categories: List[str] = []
    reasons: List[str] = []

    if path.suffix.lower() in SUPPORTED_DOC_EXTENSIONS:
        score += 0.15
        reasons.append("supported_document_type")

    if any(term in blob for term in MAIN_TERMS):
        score += 0.45
        categories.append("main_documents")
        reasons.append("main_document_signal")

    if any(term in blob for term in BOQ_TERMS):
        score += 0.40
        categories.append("boq_candidate_files")
        reasons.append("boq_or_pricing_signal")

    if any(term in blob for term in PRICING_TERMS):
        score += 0.35
        categories.append("pricing_schedule_files")
        reasons.append("pricing_schedule_signal")

    if any(term in blob for term in SBD_TERMS):
        score += 0.35
        categories.append("sbd_files")
        reasons.append("sbd_signal")

    if any(term in blob for term in SPEC_TERMS):
        score += 0.30
        categories.append("specification_files")
        reasons.append("specification_signal")

    if any(term in blob for term in RETURNABLE_TERMS):
        score += 0.25
        categories.append("returnable_files")
        reasons.append("returnable_signal")

    if any(term in blob for term in TERMS_TERMS):
        score += 0.25
        categories.append("terms_conditions_files")
        reasons.append("terms_conditions_signal")

    if any(term in blob for term in SHEQ_TERMS):
        score += 0.22
        categories.append("sheq_files")
        reasons.append("sheq_signal")

    if not categories:
        categories.append("other_files")

    # NECSA packs often use "1. Main.docx" and "2. SBD Forms.docx"; boost numbered docs.
    if re.match(r"^\s*1[\.\-_ ]+main", name):
        score += 0.25
        if "main_documents" not in categories:
            categories.append("main_documents")
        reasons.append("numbered_main_document")

    if re.match(r"^\s*2[\.\-_ ]+sbd", name):
        score += 0.20
        if "sbd_files" not in categories:
            categories.append("sbd_files")
        reasons.append("numbered_sbd_document")

    return {
        "score": round(min(score, 1.0), 4),
        "categories": list(dict.fromkeys(categories)),
        "reasons": list(dict.fromkeys(reasons)),
    }


def _file_record(path: Path, source_zip: Path, original_member: str) -> Dict[str, Any]:
    stat = path.stat()
    scoring = _score_file(path)

    return {
        "path": str(path),
        "filename": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "source_zip": str(source_zip),
        "original_member": original_member,
        "score": scoring["score"],
        "categories": scoring["categories"],
        "reasons": scoring["reasons"],
    }


def _classify_files(extracted_files: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    groups = {
        "main_documents": [],
        "boq_candidate_files": [],
        "pricing_schedule_files": [],
        "sbd_files": [],
        "specification_files": [],
        "returnable_files": [],
        "terms_conditions_files": [],
        "sheq_files": [],
        "other_files": [],
    }

    for record in extracted_files:
        categories = record.get("categories") if isinstance(record.get("categories"), list) else ["other_files"]
        added = False

        for category in categories:
            if category in groups:
                groups[category].append(record)
                added = True

        if not added:
            groups["other_files"].append(record)

    for key in groups:
        groups[key].sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)

    return groups


def _extract_single_zip(zip_entry: Dict[str, Any], run_dir: Path) -> Dict[str, Any]:
    zip_path = Path(_safe_str(zip_entry.get("path")))
    result: Dict[str, Any] = {
        "zip_path": str(zip_path),
        "status": "pending",
        "extracted_files": [],
        "rejected_members": [],
        "error": "",
    }

    if not zip_path.exists():
        result.update({"status": "failed", "error": "zip_file_not_found"})
        return result

    zip_run_dir = run_dir / _slug(zip_path.stem)
    zip_run_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            members = z.infolist()[:MAX_ZIP_MEMBERS]

            for info in members:
                name = info.filename

                if info.is_dir():
                    continue

                if not _is_safe_zip_member(name):
                    result["rejected_members"].append({
                        "name": name,
                        "reason": "unsafe_or_rejected_member",
                    })
                    continue

                if info.file_size > MAX_SINGLE_FILE_BYTES:
                    result["rejected_members"].append({
                        "name": name,
                        "reason": "file_too_large",
                        "size_bytes": info.file_size,
                    })
                    continue

                target_rel = _clean_member_name(name)
                target_path = _unique_path(zip_run_dir / target_rel)
                target_path.parent.mkdir(parents=True, exist_ok=True)

                with z.open(info, "r") as src, target_path.open("wb") as dst:
                    shutil.copyfileobj(src, dst)

                if target_path.suffix.lower() in REJECT_EXTENSIONS:
                    result["rejected_members"].append({
                        "name": name,
                        "path": str(target_path),
                        "reason": "rejected_extension_after_extract",
                    })
                    try:
                        target_path.unlink()
                    except Exception:
                        pass
                    continue

                result["extracted_files"].append(_file_record(target_path, zip_path, name))

        result["status"] = "ok"

    except Exception as exc:
        result.update({"status": "failed", "error": str(exc)})

    return result


def extract_zip_contents(acquisition_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for ZIP CONTENT EXTRACTION ENGINE.

    It extracts downloaded ZIP packages from RFQ document acquisition, classifies
    the contents, and returns prioritized paths for downstream BOQ/SBD/spec flows.
    """
    _ensure_dirs()

    if not isinstance(acquisition_result, dict):
        acquisition_result = {}

    title = _safe_str(acquisition_result.get("title") or acquisition_result.get("buyer_rfq_number") or "rfq")
    run_slug = _slug(title)
    run_dir = EXTRACTED_DIR / run_slug
    run_dir.mkdir(parents=True, exist_ok=True)

    zip_files = _locate_zip_files(acquisition_result)

    zip_results: List[Dict[str, Any]] = []
    extracted_files: List[Dict[str, Any]] = []

    for zip_entry in zip_files:
        zip_result = _extract_single_zip(zip_entry, run_dir)
        zip_results.append(zip_result)
        extracted_files.extend(zip_result.get("extracted_files") or [])

    classified = _classify_files(extracted_files)

    main_documents = classified["main_documents"]
    sbd_files = classified["sbd_files"]
    boq_files = classified["boq_candidate_files"]
    pricing_files = classified["pricing_schedule_files"]
    spec_files = classified["specification_files"]

    main_document_path = main_documents[0]["path"] if main_documents else ""
    sbd_document_paths = [x["path"] for x in sbd_files]
    boq_candidate_paths = [x["path"] for x in boq_files]
    pricing_schedule_paths = [x["path"] for x in pricing_files]
    specification_paths = [x["path"] for x in spec_files]

    confidence = 0.0
    if zip_files:
        confidence += 0.20
    if extracted_files:
        confidence += 0.25
    if main_document_path:
        confidence += 0.20
    if sbd_document_paths:
        confidence += 0.15
    if boq_candidate_paths or pricing_schedule_paths:
        confidence += 0.15
    if specification_paths:
        confidence += 0.05

    confidence = round(min(confidence, 1.0), 4)

    result: Dict[str, Any] = {
        "status": "ok" if extracted_files else "no_zip_contents_extracted",
        "engine_version": ENGINE_VERSION,
        "extracted_at": _now_iso(),
        "title": title,
        "buyer_name": _safe_str(acquisition_result.get("buyer_name")),
        "buyer_rfq_number": _safe_str(acquisition_result.get("buyer_rfq_number")),
        "zip_file_count": len(zip_files),
        "extracted_file_count": len(extracted_files),
        "zip_results": zip_results,
        "extracted_files": extracted_files,
        "classified_files": classified,
        "main_document_path": main_document_path,
        "sbd_document_paths": sbd_document_paths,
        "boq_candidate_paths": boq_candidate_paths,
        "pricing_schedule_paths": pricing_schedule_paths,
        "specification_paths": specification_paths,
        "confidence": confidence,
    }

    report_path = REPORT_DIR / f"{run_slug}__zip_content_extraction_report.json"
    report_path.write_text(json.dumps(result, indent=2, default=str))
    result["report_path"] = str(report_path)

    return result


def extract_rfq_zip_contents(acquisition_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Alias for API compatibility.
    """
    return extract_zip_contents(acquisition_result)


def get_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "runtime_dir": str(RUNTIME_DIR),
        "extracted_dir": str(EXTRACTED_DIR),
        "report_dir": str(REPORT_DIR),
        "capabilities": [
            "locate_downloaded_zip_files",
            "safe_zip_extraction",
            "reject_macos_metadata",
            "reject_unsafe_paths",
            "reject_logos_images_media",
            "classify_main_documents",
            "classify_boq_candidate_files",
            "classify_pricing_schedule_files",
            "classify_sbd_files",
            "classify_specification_files",
            "classify_returnables_terms_sheq",
            "return_prioritized_paths",
            "confidence_scoring",
            "write_json_report",
        ],
    }
