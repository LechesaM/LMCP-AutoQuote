from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import json
import os
import re
import uuid

RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "rfq_lifecycle"
STATE_FILE = RUNTIME_DIR / "rfqs.json"
UPLOAD_DRY_RUN_DIR = RUNTIME_DIR / "upload_dry_runs"
MONTHLY_QUOTES_DIR = Path("monthly_quotes")
COMPLETED_FORMS_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "tender_form_intelligence" / "completed_forms"
SUPPORTED_UPLOAD_ARTIFACT_EXTENSIONS = {".xlsx", ".xls", ".csv", ".pdf", ".docx"}
SBD_FORM_EXTENSIONS = {".pdf", ".doc", ".docx"}
GLOBAL_ARTIFACT_FALLBACK_LIMIT = 25

GLOBAL_ARTIFACT_ROOTS = [
    MONTHLY_QUOTES_DIR,
    RUNTIME_DIR / "quote_packs",
    Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "quote_pack_v44",
    Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "submission_pack_v45",
    Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "auto_submission_v46",
    Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "portal_submission_v47",
    Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "rfq_boq_extraction",
    Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "rfq_document_acquisition",
    Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "tender_document_acquisition",
    Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "rfq_document_intelligence",
    Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "rfq_docx_main_document_intelligence",
    Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "multi_portal_discovery" / "documents",
    COMPLETED_FORMS_DIR,
]

BUYER_FORM_KEYWORDS = (
    "buyer form",
    "buyer_form",
    "returnable",
    "returnable schedule",
    "returnable document",
    "bid document",
    "bidding document",
    "rfq document",
    "tender document",
    "invitation to quote",
    "invitation to bid",
    "quotation form",
    "quote form",
    "form of offer",
    "offer form",
    "authority form",
    "declaration form",
    "compulsory form",
    "mandatory form",
    "annexure",
    "addendum",
    "specification",
)
PRICING_SCHEDULE_KEYWORDS = (
    "pricing schedule",
    "price schedule",
    "pricing_schedule",
    "price_schedule",
    "buyer pricing schedule",
    "buyer_pricing_schedule",
    "bill of quantities",
    "bill_of_quantities",
    "boq",
    "b.o.q",
    "schedule of rates",
    "schedule_of_rates",
    "rates schedule",
    "rate schedule",
    "activity schedule",
    "quotation schedule",
    "quote schedule",
    "pricing table",
    "pricing_table",
    "clean pricing",
    "clean_pricing",
)
SBD_KEYWORDS = (
    "sbd",
    "standard bidding document",
    "completed_form",
    "completed-form",
    "declaration-of-interest",
)
GENERIC_MATCH_TOKENS = {
    "rfq",
    "quote",
    "tender",
    "bid",
    "supply",
    "delivery",
    "services",
    "service",
    "activities",
    "administrative",
    "support",
    "etenders",
    "etenders-web",
    "web",
}

SAFE_MODE = {
    "no_email_send": True,
    "no_portal_upload": True,
    "no_final_submit": True,
    "no_captcha_bypass": True,
    "controlled_dry_run_only": True,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any) -> str:
    try:
        if value is None:
            return ""
        return str(value).strip()
    except Exception:
        return ""


def _slug(value: Any, limit: int = 120) -> str:
    text = _safe_str(value)
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return (text[:limit].strip("-") or "rfq")


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _normalise_path(value: Any) -> Path:
    """
    Convert Docker-style /app paths and local relative paths into paths that
    resolve correctly from the LMCP project root on the host.
    """
    raw = _safe_str(value)
    if not raw:
        return Path("")

    if raw == "/app":
        raw = "."
    elif raw.startswith("/app/"):
        raw = raw[5:]

    return Path(raw)


def _normalised_path_key(path: Path) -> str:
    try:
        return str(path.resolve())
    except Exception:
        return str(path)


def _searchable_path_text(path: Path) -> str:
    text = str(path).lower().replace("_", "-")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _token_words(value: Any) -> List[str]:
    text = _slug(value, 180)
    return [part for part in text.split("-") if len(part) >= 3 and not part.isdigit()]


def _rfq_match_tokens(item: Dict[str, Any]) -> List[str]:
    raw_values = [
        _rfq_id(item),
        item.get("title"),
        item.get("description"),
        item.get("buyer_rfq_number"),
        item.get("rfq_number"),
        item.get("reference_number"),
        item.get("document_number"),
        item.get("quote_number"),
        item.get("buyer_name") or item.get("buyer") or item.get("source"),
    ]

    tokens = set()
    for value in raw_values:
        safe = _safe_str(value)
        slug = _slug(safe, 160)
        if slug and slug not in GENERIC_MATCH_TOKENS:
            tokens.add(slug)
        compact = re.sub(r"[^A-Za-z0-9]+", "", safe).lower()
        if len(compact) >= 5:
            tokens.add(compact)

    for value in raw_values[:4]:
        words = _token_words(value)
        if len(words) >= 2:
            phrase = "-".join(words[:5])
            if phrase not in GENERIC_MATCH_TOKENS:
                tokens.add(phrase)

    return sorted(tokens, key=len, reverse=True)


def _existing_path(path: Path) -> bool:
    try:
        return bool(path and path.exists())
    except Exception:
        return False


def _state_items() -> List[Dict[str, Any]]:
    """
    Supports both older list-based lifecycle stores and current dict-based
    stores such as {"items": {"rfq-id": {...}}}.
    """
    data = _read_json(STATE_FILE, {})

    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]

    if isinstance(data, dict):
        for key in ("items", "rfqs", "records", "data"):
            value = data.get(key)

            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]

            if isinstance(value, dict):
                return [x for x in value.values() if isinstance(x, dict)]

        values = list(data.values())
        if values and all(isinstance(x, dict) for x in values):
            return [x for x in values if isinstance(x, dict)]

    return []


def _rfq_id(item: Dict[str, Any]) -> str:
    return (
        _safe_str(item.get("rfq_id"))
        or _safe_str(item.get("id"))
        or _safe_str(item.get("buyer_rfq_number"))
        or _slug(item.get("title") or item.get("description"))
    )


def _state(item: Dict[str, Any]) -> str:
    return (
        _safe_str(item.get("state"))
        or _safe_str(item.get("lifecycle_state"))
        or _safe_str(item.get("current_state"))
    ).upper()


def _candidate_file_paths(item: Dict[str, Any]) -> List[Path]:
    paths: List[Path] = []

    def add(value: Any) -> None:
        if not value:
            return

        if isinstance(value, str):
            paths.append(_normalise_path(value))
            return

        if isinstance(value, list):
            for row in value:
                add(row)
            return

        if isinstance(value, dict):
            for key in (
                "path",
                "file_path",
                "quote_pack_path",
                "sbd_path",
                "sbd_form",
                "sbd_forms",
                "sbd_completed_file",
                "sbd_completed_files",
                "buyer_form_path",
                "buyer_forms",
                "buyer_document",
                "buyer_documents",
                "buyer_document_path",
                "pricing_schedule_path",
                "pricing_schedule",
                "pricing_schedules",
                "boq_path",
                "boq_paths",
                "boq",
                "boqs",
                "proof_manifest",
                "proof_archive",
                "manifest_path",
                "pdf_path",
                "output_path",
                "output_pdf",
                "completed_pdf",
                "completed_form",
                "completed_form_path",
            ):
                if value.get(key):
                    add(value.get(key))

    for key in (
        "quote_pack_path",
        "quote_pack",
        "quote_pack_files",
        "submission_pack",
        "submission_pack_path",
        "buyer_forms",
        "buyer_form_path",
        "buyer_documents",
        "buyer_document_path",
        "returnable_forms",
        "sbd_forms",
        "sbd_completed_files",
        "pricing_schedule_path",
        "pricing_schedule",
        "pricing_schedules",
        "boq_path",
        "boq_paths",
        "boq",
        "boqs",
        "proof_manifest",
        "proof_archive",
        "downloaded_files",
        "documents",
        "files",
        "attachments",
        "artifact_paths",
        "output_pdf",
        "completed_pdf",
    ):
        add(item.get(key))

    return paths


def _dedupe_paths(paths: List[Path]) -> List[Path]:
    seen = set()
    unique: List[Path] = []

    for path in paths:
        key = _normalised_path_key(path)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(path)

    return unique


def _file_matches_tokens(path: Path, tokens: List[str]) -> bool:
    low = _searchable_path_text(path)
    name = path.name.lower()

    if any(token and token in low for token in tokens):
        return True

    compact = re.sub(r"[^a-z0-9]+", "", str(path).lower())
    if any(token and len(token) >= 5 and token in compact for token in tokens):
        return True

    if "proof_archive_manifest.json" in name and any(token and token in low for token in tokens):
        return True

    return False


def _supported_upload_artifact(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_UPLOAD_ARTIFACT_EXTENSIONS


def _contains_any_keyword(path: Path, keywords: tuple[str, ...]) -> bool:
    text = f"{str(path)} {path.stem}".lower().replace("_", " ")
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    return any(keyword.replace("_", " ").lower() in text for keyword in keywords)


def _is_pricing_schedule(path: Path) -> bool:
    return _supported_upload_artifact(path) and _contains_any_keyword(path, PRICING_SCHEDULE_KEYWORDS)


def _is_sbd_form(path: Path) -> bool:
    return path.suffix.lower() in SBD_FORM_EXTENSIONS and _contains_any_keyword(path, SBD_KEYWORDS)


def _is_buyer_form(path: Path) -> bool:
    if not _supported_upload_artifact(path):
        return False
    if _is_pricing_schedule(path) or _is_sbd_form(path):
        return False
    return _contains_any_keyword(path, BUYER_FORM_KEYWORDS)


def _expand_existing_paths(paths: List[Path]) -> List[Path]:
    expanded: List[Path] = []

    for path in paths:
        if not _existing_path(path):
            continue
        try:
            if path.is_dir():
                for child in path.rglob("*"):
                    if child.is_file():
                        expanded.append(child)
            else:
                expanded.append(path)
        except Exception:
            continue

    return expanded


def _collect_global_typed_artifacts(tokens: List[str]) -> List[Path]:
    artifacts: List[Path] = []

    for root in GLOBAL_ARTIFACT_ROOTS:
        if not root.exists():
            continue

        try:
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if not _file_matches_tokens(path, tokens):
                    continue
                if _is_pricing_schedule(path) or _is_buyer_form(path):
                    artifacts.append(path)
        except Exception:
            continue

    try:
        return sorted(artifacts, key=lambda x: x.stat().st_mtime, reverse=True)[:GLOBAL_ARTIFACT_FALLBACK_LIMIT]
    except Exception:
        return artifacts[:GLOBAL_ARTIFACT_FALLBACK_LIMIT]


def _collect_global_completed_forms(tokens: List[str]) -> List[Path]:
    """
    Completed SBD forms are sometimes generated in one global folder instead of
    inside a specific RFQ quote-pack folder. Search that folder explicitly.

    Matching is preferred, but when there are only a few completed forms, include
    them as global fallback evidence so upload readiness does not stay blind to
    generated SBD artifacts.
    """
    if not COMPLETED_FORMS_DIR.exists():
        return []

    all_forms: List[Path] = []
    matched: List[Path] = []

    try:
        for path in COMPLETED_FORMS_DIR.rglob("*"):
            if not path.is_file():
                continue

            if path.suffix.lower() not in SBD_FORM_EXTENSIONS:
                continue

            all_forms.append(path)

            if _file_matches_tokens(path, tokens):
                matched.append(path)
    except Exception:
        return []

    if matched:
        return matched

    try:
        return sorted(all_forms, key=lambda x: x.stat().st_mtime, reverse=True)[:10]
    except Exception:
        return all_forms[:10]


def _find_related_files(item: Dict[str, Any]) -> Dict[str, List[str]]:
    found = {
        "quote_packs": [],
        "buyer_forms": [],
        "sbd_forms": [],
        "pricing_schedules": [],
        "proof_manifests": [],
        "other_documents": [],
    }

    tokens = _rfq_match_tokens(item)

    candidates: List[Path] = []
    candidates.extend(_expand_existing_paths(_candidate_file_paths(item)))

    # Completed SBD output and buyer/pricing artifacts can be global outputs
    # rather than children of a single RFQ folder.
    candidates.extend(_collect_global_completed_forms(tokens))
    candidates.extend(_collect_global_typed_artifacts(tokens))

    for root in GLOBAL_ARTIFACT_ROOTS:
        if not root.exists():
            continue

        try:
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if _file_matches_tokens(path, tokens):
                    candidates.append(path)
        except Exception:
            continue

    candidates = _dedupe_paths(candidates)

    seen = set()
    for path in candidates:
        if not _existing_path(path):
            continue

        key = _normalised_path_key(path)
        if key in seen:
            continue
        seen.add(key)

        low = str(path).lower()
        name = path.name.lower()

        if "proof_archive_manifest" in low or ("proof" in low and low.endswith(".json")):
            found["proof_manifests"].append(key)

        elif "quote" in low and low.endswith((".pdf", ".zip", ".json")):
            found["quote_packs"].append(key)

        elif _is_sbd_form(path) or name.endswith("_completed_form.pdf"):
            found["sbd_forms"].append(key)

        elif _is_pricing_schedule(path):
            found["pricing_schedules"].append(key)

        elif _is_buyer_form(path):
            found["buyer_forms"].append(key)

        else:
            found["other_documents"].append(key)

    return found


def _score_readiness(files: Dict[str, List[str]]) -> Dict[str, Any]:
    required = {
        "quote_packs": "Quote pack / quotation file",
        "proof_manifests": "Existing proof manifest / proof archive",
    }
    recommended = {
        "buyer_forms": "Buyer forms",
        "sbd_forms": "Completed SBD forms",
        "pricing_schedules": "Pricing schedule / BOQ",
    }

    missing_required = [label for key, label in required.items() if not files.get(key)]
    missing_recommended = [label for key, label in recommended.items() if not files.get(key)]

    score = 100
    score -= 35 * len(missing_required)
    score -= 10 * len(missing_recommended)
    score = max(0, min(100, score))

    if missing_required:
        status = "not_ready"
    elif missing_recommended:
        status = "operator_review_required"
    else:
        status = "ready_for_operator_upload_rehearsal"

    return {
        "upload_readiness_score": score,
        "upload_readiness_status": status,
        "missing_required": missing_required,
        "missing_recommended": missing_recommended,
    }


def _operator_checklist(readiness: Dict[str, Any], files: Dict[str, List[str]]) -> List[str]:
    checklist = [
        "Confirm buyer portal/login is available.",
        "Confirm RFQ closing date and time are still valid.",
        "Confirm quotation values and margins are approved.",
        "Confirm uploaded files match buyer requirements.",
        "Confirm no final submit is performed during dry-run.",
    ]

    if readiness.get("missing_required"):
        checklist.insert(0, "Resolve missing required files before upload rehearsal.")

    if files.get("sbd_forms"):
        checklist.append("Verify SBD forms are signed and correctly completed.")

    if files.get("pricing_schedules"):
        checklist.append("Verify pricing schedule matches buyer template.")

    return checklist


def run_upload_dry_run(limit: int = 5, dry_run: bool = True) -> Dict[str, Any]:
    started_at = _now_iso()
    UPLOAD_DRY_RUN_DIR.mkdir(parents=True, exist_ok=True)

    items = _state_items()
    eligible_states = {"SUBMISSION_READY", "PROOF_CAPTURED", "QUOTE_PACK_READY"}
    eligible = [item for item in items if _state(item) in eligible_states]
    selected = eligible[: max(1, int(limit or 5))]

    report_items: List[Dict[str, Any]] = []
    ready_count = 0
    missing_documents_count = 0

    for item in selected:
        rid = _rfq_id(item)
        files = _find_related_files(item)
        readiness = _score_readiness(files)

        if readiness["upload_readiness_score"] >= 70 and not readiness["missing_required"]:
            ready_count += 1

        if readiness["missing_required"] or readiness["missing_recommended"]:
            missing_documents_count += 1

        report_items.append(
            {
                "rfq_id": rid,
                "title": item.get("title") or item.get("description") or rid,
                "buyer_name": item.get("buyer_name") or item.get("buyer") or item.get("source"),
                "state": _state(item),
                "files": files,
                **readiness,
                "operator_action_checklist": _operator_checklist(readiness, files),
                "safety": SAFE_MODE,
            }
        )

    average_score = round(
        sum(float(row.get("upload_readiness_score") or 0.0) for row in report_items) / max(len(report_items), 1),
        2,
    )

    run_id = f"upload-dry-run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out_dir = UPLOAD_DRY_RUN_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "upload_dry_run_report.json"

    payload = {
        "status": "ok",
        "mode": "controlled_upload_dry_run_no_submission",
        "dry_run": bool(dry_run),
        "started_at": started_at,
        "completed_at": _now_iso(),
        "selected_count": len(selected),
        "eligible_count": len(eligible),
        "ready_count": ready_count,
        "missing_documents_count": missing_documents_count,
        "upload_readiness_score": average_score,
        "operator_action_required": True,
        "items": report_items,
        "report_path": str(report_path),
        "safety": SAFE_MODE,
    }

    _write_json(report_path, payload)
    _write_json(UPLOAD_DRY_RUN_DIR / "latest_upload_dry_run.json", payload)
    return payload


def latest_upload_dry_run_status() -> Dict[str, Any]:
    latest = _read_json(UPLOAD_DRY_RUN_DIR / "latest_upload_dry_run.json", {})
    if isinstance(latest, dict) and latest:
        return latest

    return {
        "status": "not_run",
        "mode": "controlled_upload_dry_run_no_submission",
        "upload_readiness_score": 0.0,
        "ready_count": 0,
        "missing_documents_count": 0,
        "safety": SAFE_MODE,
    }
