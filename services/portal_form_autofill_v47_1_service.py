from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import re
import traceback

SERVICE_VERSION = "V47_1_PORTAL_FORM_AUTOFILL_ASSISTANT"
DEFAULT_OUTPUT_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "portal_form_autofill_v47_1"

DEFAULT_COMPANY_PROFILE = {
    "company_name": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
    "contact_person": "Lechesa Manaba",
    "email": "lechesam@icloud.com",
    "alternate_email": "lechesam@me.com",
    "telephone": "0826338492",
    "country": "South Africa",
    "currency": "ZAR",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: Any, fallback: str = "RFQ") -> str:
    text = str(value or fallback).strip()
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-")
    return text or fallback


def _resolve_path(value: str | Path) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


def _read_json(path_value: str | Path) -> Dict[str, Any]:
    path = _resolve_path(path_value)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_portal_manifest(portal_manifest_json: str) -> Dict[str, Any]:
    path = _resolve_path(portal_manifest_json)
    if not path.exists():
        raise FileNotFoundError(f"Portal manifest JSON not found: {path}")
    data = _read_json(path)
    data["_source_portal_manifest_json"] = str(path)
    return data


def _infer_file_type(filename: str) -> str:
    f = filename.lower()
    if "quotation" in f or "quote" in f:
        return "quotation"
    if "pricing" in f or "schedule" in f:
        return "pricing_schedule"
    if "csd" in f:
        return "csd_report"
    if "bbbee" in f or "b-bbee" in f:
        return "bbbee_certificate"
    if "tax" in f:
        return "tax_compliance"
    if "company" in f or "reg" in f:
        return "company_registration"
    if "id_" in f or "id " in f or "director" in f:
        return "director_id"
    return "supporting_document"


def _extract_upload_files(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    files = []
    for item in manifest.get("upload_files") or []:
        if item.get("copy_status") == "copied" and item.get("copied_to"):
            files.append({
                "filename": item.get("filename"),
                "path": item.get("copied_to"),
                "type": _infer_file_type(item.get("filename") or item.get("copied_to")),
                "extension": item.get("extension"),
                "size_bytes": item.get("size_bytes"),
            })
    return files


def _build_form_values(
    manifest: Dict[str, Any],
    company_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    profile = {**DEFAULT_COMPANY_PROFILE, **(company_profile or {})}
    return {
        "buyer_rfq_number": manifest.get("buyer_rfq_number"),
        "quote_number": manifest.get("quote_number"),
        "buyer_name": manifest.get("buyer_name"),
        "portal_url": manifest.get("portal_url"),
        "portal_type": manifest.get("portal_type"),
        "company_name": profile.get("company_name"),
        "contact_person": profile.get("contact_person"),
        "email": profile.get("email"),
        "alternate_email": profile.get("alternate_email"),
        "telephone": profile.get("telephone"),
        "country": profile.get("country"),
        "currency": profile.get("currency"),
        "declaration_confirmed": False,
        "operator_final_review_required": True,
    }


def _build_selector_candidates() -> List[Dict[str, Any]]:
    return [
        {"field": "buyer_rfq_number", "selectors": ["input[name*='tender']", "input[name*='rfq']", "input[id*='tender']", "input[id*='rfq']"]},
        {"field": "company_name", "selectors": ["input[name*='company']", "input[id*='company']", "input[name*='supplier']", "input[id*='supplier']"]},
        {"field": "contact_person", "selectors": ["input[name*='contact']", "input[id*='contact']", "input[name*='person']"]},
        {"field": "email", "selectors": ["input[type='email']", "input[name*='email']", "input[id*='email']"]},
        {"field": "telephone", "selectors": ["input[name*='phone']", "input[id*='phone']", "input[name*='tel']", "input[id*='tel']"]},
    ]


def _portal_field_hint(file_type: str) -> str:
    hints = {
        "quotation": "Quotation / Bid Document / Price Offer upload field",
        "pricing_schedule": "Pricing Schedule / BOQ / Financial Offer upload field",
        "csd_report": "CSD / Supplier Registration document field",
        "bbbee_certificate": "B-BBEE / Specific Goals supporting document field",
        "tax_compliance": "Tax Compliance / SARS PIN document field",
        "company_registration": "Company Registration / CIPC field",
        "director_id": "Director ID / Identity Document field",
        "supporting_document": "Other supporting documents field",
    }
    return hints.get(file_type, "Supporting document upload field")


def _build_upload_instructions(upload_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    instructions = []
    for idx, f in enumerate(upload_files, start=1):
        instructions.append({
            "step": idx,
            "file_type": f["type"],
            "filename": f["filename"],
            "path": f["path"],
            "action": f"Upload {f['filename']} as {f['type']}.",
            "portal_field_hint": _portal_field_hint(f["type"]),
            "proof_required": True,
        })
    return instructions


def _build_playwright_plan(form_values: Dict[str, Any], upload_files: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "mode": "assist_only",
        "auto_submit": False,
        "captcha_bypass": False,
        "operator_confirmation_required": True,
        "field_fill_candidates": [
            {
                "field": row["field"],
                "value": form_values.get(row["field"]),
                "selectors": row["selectors"],
                "action": "fill_if_visible",
            }
            for row in _build_selector_candidates()
        ],
        "upload_candidates": [
            {
                "file_type": f["type"],
                "path": f["path"],
                "filename": f["filename"],
                "action": "set_input_files_after_operator_confirms_correct_upload_field",
            }
            for f in upload_files
        ],
        "blocked_actions": [
            "Do not click final submit automatically.",
            "Do not bypass CAPTCHA.",
            "Do not upload ZIP files unless buyer-specific rules are later added.",
        ],
    }


def generate_portal_form_autofill_plan(
    portal_manifest_json: str,
    company_profile: Optional[Dict[str, Any]] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    started_at = _now_iso()
    try:
        manifest = _load_portal_manifest(portal_manifest_json)
        rfq = manifest.get("buyer_rfq_number") or "RFQ"
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        out_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        if not out_root.is_absolute():
            out_root = Path.cwd() / out_root
        workspace = out_root / f"{_safe_name(rfq)}__AUTOFILL-{timestamp}"
        workspace.mkdir(parents=True, exist_ok=True)

        # V47.1.1: Resolve RFQ-specific eTenders detail URL before building the plan.
        # If V50.7 finds a strong detail link, use it instead of the generic portal homepage.
        navigation_resolution = None
        resolved_portal_url = (
            manifest.get("detail_url")
            or manifest.get("opportunity_url")
            or manifest.get("source_url")
            or manifest.get("portal_url")
        )

        try:
            from app.services.etenders_real_detail_navigation_v50_7_service import analyse_etenders_detail_navigation

            navigation_resolution = analyse_etenders_detail_navigation({
                "buyer_rfq_number": rfq,
                "title": manifest.get("title") or manifest.get("description") or rfq,
                "description": manifest.get("description") or "",
                "raw_text": manifest.get("raw_text") or "",
                "portal_url": resolved_portal_url or "https://www.etenders.gov.za/Home/opportunities?id=1",
                "source_url": manifest.get("source_url") or "",
                "detail_url": manifest.get("detail_url") or "",
            })

            detail_links = navigation_resolution.get("recommended_detail_links") or []
            if detail_links and detail_links[0].get("url"):
                resolved_portal_url = detail_links[0]["url"]

            # V50.8.3 fallback: structured DataTables JSON resolver can reconstruct
            # TenderDetails and Esubmission URLs from row-local tender IDs.
            if not detail_links:
                try:
                    from app.services.etenders_structured_json_parser_v50_8_3_service import parse_etenders_structured_json

                    structured_resolution = parse_etenders_structured_json({
                        "title": manifest.get("title") or manifest.get("description") or rfq,
                        "buyer_rfq_number": rfq,
                        "description": manifest.get("description") or "",
                        "raw_text": manifest.get("raw_text") or "",
                        "source_url": resolved_portal_url or "https://www.etenders.gov.za/Home/opportunities?id=1",
                    })

                    navigation_resolution["structured_resolution"] = structured_resolution

                    candidates = (
                        structured_resolution.get("recommended_detail_links")
                        or structured_resolution.get("recommended_links")
                        or structured_resolution.get("candidate_links")
                        or []
                    )

                    preferred = None
                    for c in candidates:
                        url = str(c.get("url") or "")
                        if "esubmission" in url.lower():
                            preferred = url
                            break
                    if not preferred:
                        for c in candidates:
                            url = str(c.get("url") or "")
                            if "tenderdetails" in url.lower():
                                preferred = url
                                break
                    if not preferred:
                        for c in candidates:
                            url = str(c.get("url") or "")
                            if url and "download" not in url.lower():
                                preferred = url
                                break

                    if preferred:
                        resolved_portal_url = preferred

                except Exception as exc:
                    navigation_resolution["structured_resolution_error"] = str(exc)

            # V50.8.3 fallback: structured DataTables JSON resolver can reconstruct
            # TenderDetails and Esubmission URLs from row-local tender IDs.
            if not detail_links:
                try:
                    from app.services.etenders_structured_json_parser_v50_8_3_service import parse_etenders_structured_json

                    structured_resolution = parse_etenders_structured_json({
                        "title": manifest.get("title") or manifest.get("description") or rfq,
                        "buyer_rfq_number": rfq,
                        "description": manifest.get("description") or "",
                        "raw_text": manifest.get("raw_text") or "",
                        "source_url": resolved_portal_url or "https://www.etenders.gov.za/Home/opportunities?id=1",
                    })

                    navigation_resolution["structured_resolution"] = structured_resolution

                    candidates = (
                        structured_resolution.get("recommended_detail_links")
                        or structured_resolution.get("recommended_links")
                        or structured_resolution.get("candidate_links")
                        or []
                    )

                    # Prefer eSubmission route, then TenderDetails route, then any non-download candidate.
                    preferred = None
                    for c in candidates:
                        url = str(c.get("url") or "")
                        low = url.lower()
                        if "esubmission" in low:
                            preferred = url
                            break
                    if not preferred:
                        for c in candidates:
                            url = str(c.get("url") or "")
                            low = url.lower()
                            if "tenderdetails" in low:
                                preferred = url
                                break
                    if not preferred:
                        for c in candidates:
                            url = str(c.get("url") or "")
                            low = url.lower()
                            if url and "download" not in low:
                                preferred = url
                                break

                    if preferred:
                        resolved_portal_url = preferred

                except Exception as exc:
                    navigation_resolution["structured_resolution_error"] = str(exc)

        except Exception as exc:
            navigation_resolution = {
                "status": "error",
                "message": "V50.7 detail navigation resolution failed.",
                "error": str(exc),
            }

        if resolved_portal_url:
            manifest["portal_url"] = resolved_portal_url

        upload_files = _extract_upload_files(manifest)
        form_values = _build_form_values(manifest, company_profile=company_profile)
        upload_instructions = _build_upload_instructions(upload_files)
        playwright_plan = _build_playwright_plan(form_values, upload_files)

        operator_checklist = {
            "buyer_rfq_number": rfq,
            "portal_url": resolved_portal_url,
            "checklist": [
                "Confirm correct portal and RFQ/tender record.",
                "Confirm closing date/time has not passed.",
                "Confirm all uploaded files match the RFQ and company.",
                "Confirm no ZIP file is uploaded.",
                "Confirm all mandatory portal fields are completed.",
                "Confirm declarations are correct before ticking any declaration checkbox.",
                "Submit only after final review.",
                "Save receipt and screenshots after submission.",
            ],
            "upload_instructions": upload_instructions,
        }

        result = {
            "status": "ok",
            "service_version": SERVICE_VERSION,
            "message": "Portal form auto-fill plan generated. Operator confirmation is required before any portal submission.",
            "buyer_rfq_number": rfq,
            "quote_number": manifest.get("quote_number"),
            "portal_url": resolved_portal_url,
            "portal_type": manifest.get("portal_type"),
            "navigation_resolution": navigation_resolution,
            "workspace": str(workspace),
            "source_portal_manifest_json": manifest.get("_source_portal_manifest_json"),
            "started_at": started_at,
            "completed_at": _now_iso(),
            "safety_policy": {
                "auto_submit": False,
                "captcha_bypass": False,
                "operator_confirmation_required": True,
                "zip_upload_allowed": False,
            },
            "form_values": form_values,
            "selector_candidates": _build_selector_candidates(),
            "upload_files": upload_files,
            "upload_instructions": upload_instructions,
            "playwright_plan": playwright_plan,
            "operator_checklist": operator_checklist,
            "artifacts": {
                "autofill_plan_json": str(workspace / "portal_autofill_plan_v47_1.json"),
                "playwright_plan_json": str(workspace / "playwright_autofill_plan_v47_1.json"),
                "operator_checklist_json": str(workspace / "operator_checklist_v47_1.json"),
            },
        }

        _write_json(workspace / "portal_autofill_plan_v47_1.json", result)
        _write_json(workspace / "playwright_autofill_plan_v47_1.json", playwright_plan)
        _write_json(workspace / "operator_checklist_v47_1.json", operator_checklist)

        return result

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V47.1 portal form auto-fill plan generation failed.",
            "portal_manifest_json": portal_manifest_json,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def get_v47_1_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "service": "V47.1 Portal Form Auto-Fill Assistant",
        "description": "Creates safe portal form values, selector candidates, upload instructions, and Playwright-ready assist plan. Does not submit, does not bypass CAPTCHA.",
        "default_output_dir": str(DEFAULT_OUTPUT_DIR),
        "safety_policy": {
            "auto_submit": False,
            "captcha_bypass": False,
            "operator_confirmation_required": True,
            "zip_upload_allowed": False,
        },
        "endpoints": {
            "status": "/v47-portal-autofill/status",
            "generate_plan": "/v47-portal-autofill/generate-plan",
        },
        "ready": True,
    }
