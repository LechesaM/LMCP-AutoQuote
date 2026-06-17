
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import re
import traceback

SERVICE_VERSION = "V47_7_DEEP_VERIFICATION_AUDIT_TRAIL"
_RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
DEFAULT_OUTPUT_DIR = _RUNTIME_DIR / "deep_verification_v47_7"
DEFAULT_REGISTER_PATH = _RUNTIME_DIR / "submission_history" / "v47_7_verified_submission_register.json"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: Any, fallback: str = "RFQ") -> str:
    text = str(value or fallback).strip()
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-")
    return text or fallback


def _resolve_path(value: str | Path) -> Path:
    raw = str(value)
    if raw.startswith("/app/runtime/"):
        return _RUNTIME_DIR / raw.replace("/app/runtime/", "", 1)
    p = Path(value)
    if not p.is_absolute():
        p = _RUNTIME_DIR / p
    return p


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_json_optional(path_value: Optional[str]) -> Dict[str, Any]:
    if not path_value:
        return {}
    path = _resolve_path(path_value)
    if not path.exists():
        return {"_missing_source_json": str(path)}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data["_source_json"] = str(path)
            return data
        return {"_source_json": str(path), "data": data}
    except Exception as exc:
        return {"_source_json": str(path), "_read_error": str(exc)}


def _make_workspace(buyer_rfq_number: str, output_dir: Optional[str]) -> Path:
    root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    if not root.is_absolute():
        root = Path.cwd() / root
    workspace = root / f"{_safe_name(buyer_rfq_number)}__AUDIT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    (workspace / "screenshots").mkdir(parents=True, exist_ok=True)
    return workspace


def _pick_active_page(browser: Any) -> Any:
    pages = []
    for context in browser.contexts:
        pages.extend(context.pages)
    if not pages:
        raise RuntimeError("No open pages found in attached browser.")
    return pages[-1]


def _body_text(page: Any) -> str:
    try:
        return page.locator("body").inner_text(timeout=6000)
    except Exception:
        return ""


def _norm(value: Any) -> str:
    return str(value or "").lower().strip()


def _extract_rows(page: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        tr = page.locator("table tbody tr")
        for i in range(min(tr.count(), 100)):
            try:
                row = tr.nth(i)
                cells = []
                td = row.locator("td")
                for j in range(min(td.count(), 20)):
                    cells.append(td.nth(j).inner_text(timeout=1000).strip())
                rows.append({"index": i, "text": row.inner_text(timeout=1000).strip(), "cells": cells})
            except Exception as exc:
                rows.append({"index": i, "error": str(exc)})
    except Exception as exc:
        rows.append({"error": str(exc)})
    return rows


def _matching_rows(rows: List[Dict[str, Any]], buyer_rfq_number: str, description_hint: Optional[str]) -> List[Dict[str, Any]]:
    matches = []
    rfq = _norm(buyer_rfq_number)
    desc = _norm(description_hint)
    for row in rows:
        text = _norm(row.get("text"))
        if rfq and rfq in text:
            matches.append(row)
        elif desc and desc[:35] in text:
            matches.append(row)
        elif "submitted" in text and "not submitted" not in text and ("supply" in text or "delivery" in text):
            matches.append(row)
    return matches


def _expand_row(page: Any, row_index: int) -> Dict[str, Any]:
    try:
        row = page.locator("table tbody tr").nth(row_index)
        row.locator("td").first.click(timeout=3000)
        page.wait_for_timeout(2000)
        return {"status": "expanded_or_clicked", "row_index": row_index}
    except Exception as exc:
        return {"status": "not_expanded", "row_index": row_index, "error": str(exc)}


def _assess(page_text: str, rows: List[Dict[str, Any]], matches: List[Dict[str, Any]], buyer_rfq_number: str, quote_number: Optional[str]) -> Dict[str, Any]:
    combined = _norm(page_text + "\n" + "\n".join(str(r.get("text") or "") for r in rows))
    submitted_rows = [r for r in (matches or rows) if "submitted" in _norm(r.get("text")) and "not submitted" not in _norm(r.get("text"))]
    rfq_seen = bool(buyer_rfq_number and _norm(buyer_rfq_number) in combined)
    quote_seen = bool(quote_number and _norm(quote_number) in combined)

    if submitted_rows:
        return {
            "verification_status": "verified_submitted",
            "confidence": 0.95,
            "submitted_row_found": True,
            "submitted_row": submitted_rows[0],
            "rfq_seen": rfq_seen,
            "quote_seen": quote_seen,
            "matching_rows_count": len(matches),
            "rows_detected": len(rows),
        }
    if "submitted" in combined and (rfq_seen or matches):
        return {
            "verification_status": "verified_likely_submitted",
            "confidence": 0.85,
            "submitted_row_found": False,
            "rfq_seen": rfq_seen,
            "quote_seen": quote_seen,
            "matching_rows_count": len(matches),
            "rows_detected": len(rows),
        }
    if "not submitted" in combined or "failed" in combined or "error" in combined:
        status = "not_verified_review_required"
        confidence = 0.35
    else:
        status = "unknown_review_required"
        confidence = 0.25
    return {
        "verification_status": status,
        "confidence": confidence,
        "submitted_row_found": False,
        "rfq_seen": rfq_seen,
        "quote_seen": quote_seen,
        "matching_rows_count": len(matches),
        "rows_detected": len(rows),
    }


def _append_register(register_path: str, record: Dict[str, Any]) -> None:
    path = _resolve_path(register_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        if not isinstance(data, list):
            data = []
    except Exception:
        data = []
    data.append(record)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def run_deep_verification_audit(
    buyer_rfq_number: str,
    quote_number: Optional[str] = None,
    description_hint: Optional[str] = None,
    final_submission_run_json: Optional[str] = None,
    verification_v47_6_json: Optional[str] = None,
    cdp_url: str = DEFAULT_CDP_URL,
    output_dir: Optional[str] = None,
    register_path: str = str(DEFAULT_REGISTER_PATH),
    navigate_to_profile_responses: bool = True,
    profile_responses_url: str = "https://www.etenders.gov.za/Profile#ResponsesSubmitted",
    capture_screenshots: bool = True,
    expand_matching_row: bool = True,
    wait_ms: int = 5000,
) -> Dict[str, Any]:
    started_at = _now_iso()
    try:
        final_run = _read_json_optional(final_submission_run_json)
        v47_6 = _read_json_optional(verification_v47_6_json)
        quote_number = quote_number or final_run.get("quote_number") or v47_6.get("quote_number")
        buyer_rfq_number = buyer_rfq_number or final_run.get("buyer_rfq_number") or v47_6.get("buyer_rfq_number") or "RFQ"

        workspace = _make_workspace(buyer_rfq_number, output_dir)
        screenshots_dir = workspace / "screenshots"

        from playwright.sync_api import sync_playwright

        screenshots: List[str] = []
        expand_result: Dict[str, Any] = {}
        expanded_text = ""

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            page = _pick_active_page(browser)

            if navigate_to_profile_responses:
                page.goto(profile_responses_url, wait_until="domcontentloaded", timeout=60000)

            page.wait_for_timeout(wait_ms)

            if capture_screenshots:
                s1 = screenshots_dir / "01_responses_submitted_page.png"
                page.screenshot(path=str(s1), full_page=True)
                screenshots.append(str(s1))

            page_text = _body_text(page)
            rows = _extract_rows(page)
            if "Loading..." in page_text:
                page.wait_for_timeout(5000)
                page_text = _body_text(page)
                rows = _extract_rows(page)

            matches = _matching_rows(rows, buyer_rfq_number, description_hint)

            if expand_matching_row and matches:
                expand_result = _expand_row(page, int(matches[0].get("index", 0)))
                expanded_text = _body_text(page)
                if capture_screenshots:
                    s2 = screenshots_dir / "02_after_expand_matching_row.png"
                    page.screenshot(path=str(s2), full_page=True)
                    screenshots.append(str(s2))

            final_url = page.url
            final_title = page.title()
            browser.close()

        assessment = _assess(page_text + "\n" + expanded_text, rows, matches, buyer_rfq_number, quote_number)

        audit_record = {
            "buyer_rfq_number": buyer_rfq_number,
            "quote_number": quote_number,
            "description_hint": description_hint,
            "verification_status": assessment["verification_status"],
            "confidence": assessment["confidence"],
            "verified_at": _now_iso(),
            "portal_url": final_url,
            "workspace": str(workspace),
            "screenshots": screenshots,
        }

        result = {
            "status": assessment["verification_status"],
            "service_version": SERVICE_VERSION,
            "message": "Deep verification and audit record completed.",
            "buyer_rfq_number": buyer_rfq_number,
            "quote_number": quote_number,
            "workspace": str(workspace),
            "started_at": started_at,
            "completed_at": _now_iso(),
            "live_page": {"cdp_url": cdp_url, "url": final_url, "title": final_title},
            "assessment": assessment,
            "matching_rows": matches,
            "all_rows": rows,
            "expand_result": expand_result,
            "screenshots": screenshots,
            "audit_record": audit_record,
            "artifacts": {
                "deep_verification_json": str(workspace / "deep_verification_audit_v47_7.json"),
                "screenshots_dir": str(screenshots_dir),
                "register_json": str(_resolve_path(register_path)),
            },
        }

        _write_json(workspace / "deep_verification_audit_v47_7.json", result)
        _append_register(register_path, audit_record)
        return result

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V47.7 deep verification audit failed.",
            "buyer_rfq_number": buyer_rfq_number,
            "quote_number": quote_number,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def get_v47_7_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "service": "V47.7 Deep Verification + Audit Trail Engine",
        "description": "Extracts submitted response rows, optionally expands the matching row, captures proof screenshots, writes a deep verification JSON, and appends a permanent verified submission register.",
        "default_output_dir": str(DEFAULT_OUTPUT_DIR),
        "default_register_path": str(DEFAULT_REGISTER_PATH),
        "default_cdp_url": DEFAULT_CDP_URL,
        "endpoints": {
            "status": "/v47-deep-verification/status",
            "run_audit": "/v47-deep-verification/run-audit",
        },
        "ready": True,
    }
