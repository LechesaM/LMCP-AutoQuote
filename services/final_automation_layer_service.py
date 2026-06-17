from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

SERVICE_VERSION = "V28_SELF_HEALING_FINAL_AUTOMATION_LAYER"

PROJECT_ROOT = Path(os.getenv("LMCP_PROJECT_ROOT", "/app")).resolve()
RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "final_automation_layer"
COMPLIANCE_DIR = RUNTIME_DIR / "compliance"
FINAL_AUTOMATION_DIR = RUNTIME_DIR / "final_automation"
FINAL_AUTOMATION_LOGS = FINAL_AUTOMATION_DIR / "logs"
STANDARD_CSD_REPORT = COMPLIANCE_DIR / "CSD_Report.pdf"

for folder in (COMPLIANCE_DIR, FINAL_AUTOMATION_DIR, FINAL_AUTOMATION_LOGS):
    folder.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_log(prefix: str, payload: Dict[str, Any]) -> str:
    try:
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        path = FINAL_AUTOMATION_LOGS / f"{prefix}_{stamp}.json"
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return str(path)
    except Exception:
        return ""


def _pdf_exists(path: Path) -> bool:
    try:
        return path.exists() and path.is_file() and path.suffix.lower() == ".pdf"
    except Exception:
        return False


def _find_pdf(patterns: List[str]) -> str:
    matches: List[Path] = []
    for pattern in patterns:
        for variant in {pattern, pattern.upper(), pattern.lower()}:
            try:
                matches.extend(COMPLIANCE_DIR.glob(variant))
            except Exception:
                pass

    files = [p for p in matches if _pdf_exists(p)]
    if not files:
        return ""

    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(files[0])


def _standardize_csd_if_possible(csd_path: str) -> str:
    if not csd_path:
        return ""

    source = Path(csd_path)
    if not _pdf_exists(source):
        return csd_path

    try:
        if source.resolve() != STANDARD_CSD_REPORT.resolve():
            STANDARD_CSD_REPORT.write_bytes(source.read_bytes())
        return str(STANDARD_CSD_REPORT)
    except Exception:
        return str(source)


def check_compliance_pack_readiness() -> Dict[str, Any]:
    csd_found = _find_pdf([
        "CSD_Report.pdf",
        "*CSD*.pdf",
        "*csd*.pdf",
        "*Supplier*Database*.pdf",
        "*supplier*database*.pdf",
        "new CSD report*.pdf",
        "new csd report*.pdf",
    ])
    csd_standard = _standardize_csd_if_possible(csd_found)

    docs = {
        "csd_report": csd_standard or csd_found,
        "tax_compliance": _find_pdf([
            "Tax_Compliance_Pin.pdf",
            "*TAX*.pdf",
            "*tax*.pdf",
            "*TCS*.pdf",
            "*tcs*.pdf",
            "*PIN*.pdf",
            "*pin*.pdf",
            "*SARS*.pdf",
            "*sars*.pdf",
        ]),
        "bbbee_certificate": _find_pdf([
            "BBBEE_Certificate.pdf",
            "*BBBEE*.pdf",
            "*bbbee*.pdf",
            "*B-BBEE*.pdf",
            "*BEE*.pdf",
        ]),
        "company_registration": _find_pdf([
            "*Company*Reg*.pdf",
            "*company*reg*.pdf",
            "*CIPC*.pdf",
            "*cipc*.pdf",
            "*registration*.pdf",
        ]),
        "director_id": _find_pdf([
            "*ID*.pdf",
            "*id*.pdf",
            "*director*.pdf",
            "*identity*.pdf",
        ]),
    }

    required = ["csd_report", "tax_compliance", "bbbee_certificate"]
    missing_required = [key for key in required if not docs.get(key)]
    available = {key: value for key, value in docs.items() if value}

    return {
        "status": "ready" if not missing_required else "blocked",
        "checked_at": _now(),
        "compliance_dir": str(COMPLIANCE_DIR),
        "standard_csd_report": str(STANDARD_CSD_REPORT),
        "standard_csd_report_exists": STANDARD_CSD_REPORT.exists(),
        "available_documents": available,
        "missing_required": missing_required,
        "recommended_optional_missing": [
            key for key in ["company_registration", "director_id"] if not docs.get(key)
        ],
    }


def get_csd_status() -> Dict[str, Any]:
    try:
        from app.services.csd_monthly_refresh_service import get_csd_refresh_status
        status = get_csd_refresh_status()
        status = dict(status or {})
    except Exception as exc:
        status = {"status": "unavailable", "message": str(exc)}

    status["standard_csd_report"] = str(STANDARD_CSD_REPORT)
    status["standard_csd_report_exists"] = STANDARD_CSD_REPORT.exists()
    return status


def get_autonomous_status() -> Dict[str, Any]:
    try:
        status_file = RUNTIME_DIR / "autonomous_status.json"
        if status_file.exists():
            data = json.loads(status_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass

    return {
        "status": "unknown",
        "message": "No direct autonomous status file found. This is informational only.",
    }


def final_go_live_check() -> Dict[str, Any]:
    compliance = check_compliance_pack_readiness()
    csd = get_csd_status()
    autonomous = get_autonomous_status()

    blockers = []
    if compliance.get("status") != "ready":
        blockers.append({
            "area": "compliance_pack",
            "message": "Required compliance documents are missing.",
            "missing": compliance.get("missing_required", []),
        })

    if "csd_report" in compliance.get("missing_required", []):
        blockers.append({
            "area": "csd",
            "message": "CSD report is not available. Place a CSD PDF into runtime/compliance or name it CSD_Report.pdf.",
        })

    ready = len(blockers) == 0
    result = {
        "status": "ready" if ready else "blocked",
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "ready_for_live_automation": ready,
        "blockers": blockers,
        "autonomous": autonomous,
        "csd": csd,
        "compliance": compliance,
    }
    _write_log("go_live_check", result)
    return result


def run_final_automation_once(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = payload or {}
    go_live = final_go_live_check()

    force = bool(payload.get("force", False))
    test_mode = bool(payload.get("test_mode", payload.get("pipeline_test_mode", False)))

    if go_live.get("status") != "ready" and not (force or test_mode):
        result = {
            "status": "blocked",
            "service_version": SERVICE_VERSION,
            "checked_at": _now(),
            "message": "Final automation blocked by go-live checks.",
            "go_live": go_live,
        }
        _write_log("run_blocked", result)
        return result

    errors: List[str] = []

    try:
        from app.services.tender_harvester import run_national_tender_radar
        radar_result = run_national_tender_radar(
            max_total=int(payload.get("max_total", os.getenv("TENDER_RADAR_MAX_TOTAL", 25))),
            max_per_source=int(payload.get("max_per_source", os.getenv("TENDER_RADAR_MAX_PER_SOURCE", 2))),
            enable_auto_quote=bool(payload.get("enable_auto_quote", True)),
            persist_to_live_store=bool(payload.get("persist_to_live_store", True)),
        )
        result = {
            "status": "ok",
            "service_version": SERVICE_VERSION,
            "checked_at": _now(),
            "message": "Final automation cycle completed through national tender radar.",
            "go_live": go_live,
            "result": radar_result,
        }
        _write_log("run_ok", result)
        return result
    except Exception as exc:
        errors.append(f"run_national_tender_radar failed: {exc}")

    result = {
        "status": "error",
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "message": "No final automation execution path completed.",
        "errors": errors,
        "go_live": go_live,
    }
    _write_log("run_error", result)
    return result


def get_final_automation_status() -> Dict[str, Any]:
    return final_go_live_check()
