from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from app.services.quote_compilation_service import QuoteCompilationService, append_pack_audit_event


router = APIRouter(prefix="/quote-compilation", tags=["Quote Compilation"])


def service() -> QuoteCompilationService:
    return QuoteCompilationService()


def _safe_download_filename(value: str, extension: str = "txt") -> str:
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value).strip("-")
    safe = "-".join(part for part in safe.split("-") if part)
    safe_extension = "".join(char for char in extension.lower() if char.isalnum()) or "txt"
    return f"{safe[:140] or 'submission-export'}.{safe_extension}"


@router.get("/status")
def status() -> Dict[str, Any]:
    return service().status()


@router.get("/candidates")
def candidates(limit: int = Query(default=50, ge=1, le=100)) -> Dict[str, Any]:
    return service().candidates(limit=limit)


@router.get("/packs")
def packs(limit: int = Query(default=50, ge=1, le=50)) -> Dict[str, Any]:
    return service().packs(limit=limit)


@router.get("/packs/latest")
def latest_pack() -> Dict[str, Any]:
    return service().latest_pack()


@router.get("/submission-binders")
def submission_binders(limit: int = Query(default=50, ge=1, le=50)) -> Dict[str, Any]:
    return service().submission_binders(limit=limit)


@router.get("/submission-gate/{pack_id}")
def submission_gate(pack_id: str, rfq_reference: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    return service().submission_gate(pack_id, rfq_reference=rfq_reference)


@router.get("/submission-gate/{pack_id}/checklist")
def submission_gate_checklist(
    pack_id: str,
    rfq_reference: Optional[str] = Query(default=None),
    include_text: bool = Query(default=True),
) -> Dict[str, Any]:
    return service().submission_gate_checklist(pack_id, rfq_reference=rfq_reference, include_text=include_text)


@router.get("/submission-gate/{pack_id}/checklist.txt", response_class=PlainTextResponse)
def submission_gate_checklist_text(
    pack_id: str,
    rfq_reference: Optional[str] = Query(default=None),
) -> PlainTextResponse:
    checklist = service().submission_gate_checklist(pack_id, rfq_reference=rfq_reference, include_text=True)
    filename = _safe_download_filename(f"{checklist.get('pack_id') or pack_id}-manual-submission-checklist")
    return PlainTextResponse(
        content=str(checklist.get("checklist_text") or ""),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/submission-gate/{pack_id}/audit-log")
def submission_gate_audit_log(pack_id: str, rfq_reference: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    return service().submission_gate_audit_log(pack_id, rfq_reference=rfq_reference)


@router.get("/submission-gate/{pack_id}/audit-log.json")
def submission_gate_audit_log_json(pack_id: str, rfq_reference: Optional[str] = Query(default=None)) -> JSONResponse:
    audit_log = service().submission_gate_audit_log(pack_id, rfq_reference=rfq_reference)
    filename = _safe_download_filename(f"{audit_log.get('pack_id') or pack_id}-submission-audit-log", "json")
    return JSONResponse(
        content=audit_log,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/submission-gate/{pack_id}/audit-log.txt", response_class=PlainTextResponse)
def submission_gate_audit_log_text(pack_id: str, rfq_reference: Optional[str] = Query(default=None)) -> PlainTextResponse:
    audit_log = service().submission_gate_audit_log(pack_id, rfq_reference=rfq_reference)
    filename = _safe_download_filename(f"{audit_log.get('pack_id') or pack_id}-submission-audit-log", "txt")
    return PlainTextResponse(
        content=service().submission_gate_audit_log_text(pack_id, rfq_reference=rfq_reference),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/submission-gate/{pack_id}/evidence-manifest")
def submission_gate_evidence_manifest(pack_id: str, rfq_reference: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    return service().submission_gate_evidence_manifest(pack_id, rfq_reference=rfq_reference)


@router.get("/submission-gate/{pack_id}/evidence-manifest.json")
def submission_gate_evidence_manifest_json(pack_id: str, rfq_reference: Optional[str] = Query(default=None)) -> JSONResponse:
    manifest = service().submission_gate_evidence_manifest(pack_id, rfq_reference=rfq_reference)
    filename = _safe_download_filename(f"{manifest.get('pack_id') or pack_id}-evidence-manifest", "json")
    return JSONResponse(
        content=manifest,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/submission-gate/{pack_id}/summary")
def submission_gate_summary(pack_id: str, rfq_reference: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    return service().submission_gate_summary(pack_id, rfq_reference=rfq_reference)


@router.get("/submission-gate/{pack_id}/summary.json")
def submission_gate_summary_json(pack_id: str, rfq_reference: Optional[str] = Query(default=None)) -> JSONResponse:
    summary = service().submission_gate_summary(pack_id, rfq_reference=rfq_reference)
    filename = _safe_download_filename(f"{summary.get('pack_id') or pack_id}-submission-pack-summary", "json")
    return JSONResponse(
        content=summary,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/submission-gate/{pack_id}/readiness-checklist")
def submission_gate_readiness_checklist(pack_id: str, rfq_reference: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    return service().readiness_checklist(pack_id, rfq_reference=rfq_reference)


@router.get("/submission-gate/{pack_id}/readiness-checklist.json")
def submission_gate_readiness_checklist_json(pack_id: str, rfq_reference: Optional[str] = Query(default=None)) -> JSONResponse:
    checklist = service().readiness_checklist(pack_id, rfq_reference=rfq_reference)
    append_pack_audit_event(
        checklist.get("pack_id") or pack_id,
        "readiness_checklist_json_export",
        {
            "final_status": checklist.get("final_status"),
            "can_submit_final": bool(checklist.get("can_submit_final")),
            "audit_event_count": checklist.get("audit_event_count", 0),
        },
    )
    filename = _safe_download_filename(f"{checklist.get('pack_id') or pack_id}-readiness-checklist", "json")
    return JSONResponse(
        content=checklist,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/submission-gate/{pack_id}/evidence-bundle")
def submission_gate_evidence_bundle(pack_id: str, rfq_reference: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    return service().evidence_bundle(pack_id, rfq_reference=rfq_reference)


@router.get("/submission-gate/{pack_id}/evidence-bundle.json")
def submission_gate_evidence_bundle_json(pack_id: str, rfq_reference: Optional[str] = Query(default=None)) -> JSONResponse:
    bundle = service().evidence_bundle(pack_id, rfq_reference=rfq_reference)
    append_pack_audit_event(
        bundle.get("pack_id") or pack_id,
        "evidence_bundle_json_export",
        {
            "final_submit_locked": bool(bundle.get("final_submit_locked")),
            "automated_submit_disabled": bool(bundle.get("automated_submit_disabled")),
            "audit_warning_count": bundle.get("audit_warning_count", 0),
            "bundle_warning_count": len(bundle.get("bundle_warnings") or []),
        },
    )
    filename = _safe_download_filename(f"{bundle.get('pack_id') or pack_id}-evidence-bundle", "json")
    return JSONResponse(
        content=bundle,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/submission-gate/{pack_id}/manual-completion")
def submission_gate_manual_completion(
    pack_id: str,
    payload: Optional[Dict[str, Any]] = Body(default=None),
) -> Dict[str, Any]:
    try:
        return service().save_manual_completion(pack_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/submission-gate/{pack_id}/manual-completion")
def submission_gate_manual_completion_get(pack_id: str) -> Dict[str, Any]:
    return service().manual_completion(pack_id)


@router.get("/submission-gate/{pack_id}/manual-completion.json")
def submission_gate_manual_completion_json(pack_id: str) -> JSONResponse:
    manual_completion = service().manual_completion(pack_id)
    filename = _safe_download_filename(f"{manual_completion.get('pack_id') or pack_id}-manual-completion", "json")
    record = manual_completion.get("manual_completion") if isinstance(manual_completion.get("manual_completion"), dict) else None
    content = record if isinstance(record, dict) else manual_completion
    if isinstance(record, dict) and manual_completion.get("status") == "ok":
        append_pack_audit_event(
            manual_completion.get("pack_id") or pack_id,
            "manual_completion_json_export",
            {
                "status": manual_completion.get("status"),
                "validation_status": manual_completion.get("validation", {}).get("status") if isinstance(manual_completion.get("validation"), dict) else None,
                "manual_completion_allowed": bool(manual_completion.get("validation", {}).get("allowed")) if isinstance(manual_completion.get("validation"), dict) else None,
            },
        )
    return JSONResponse(
        content=content,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/submission-gate/{pack_id}/audit-trail")
def submission_gate_audit_trail(pack_id: str) -> Dict[str, Any]:
    return service().audit_trail(pack_id)


@router.get("/submission-gate/{pack_id}/audit-trail.json")
def submission_gate_audit_trail_json(pack_id: str) -> JSONResponse:
    trail = service().audit_trail(pack_id)
    filename = _safe_download_filename(f"{trail.get('pack_id') or pack_id}-audit-trail", "json")
    return JSONResponse(
        content=trail,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/packs/{pack_id}/pricing")
def pack_pricing(pack_id: str) -> Dict[str, Any]:
    return service().pack_pricing(pack_id)


@router.post("/packs/{pack_id}/pricing/dry-run")
def pricing_dry_run(pack_id: str, payload: Optional[Dict[str, Any]] = Body(default=None)) -> Dict[str, Any]:
    return service().pricing_dry_run(pack_id, payload)


@router.post("/packs/{pack_id}/pricing/save-local")
def save_local_pricing(pack_id: str, payload: Optional[Dict[str, Any]] = Body(default=None)) -> Dict[str, Any]:
    return service().save_local_pricing(pack_id, payload)


@router.get("/packs/{pack_id}/formal-quote")
def formal_quote(pack_id: str) -> Dict[str, Any]:
    return service().formal_quote(pack_id)


@router.post("/packs/{pack_id}/formal-quote/generate-local")
def generate_local_formal_quote(pack_id: str) -> Dict[str, Any]:
    return service().generate_local_formal_quote(pack_id)


@router.get("/packs/{pack_id}/returnables")
def returnables(pack_id: str) -> Dict[str, Any]:
    return service().returnables(pack_id)


@router.post("/packs/{pack_id}/returnables/save-local")
def save_local_returnables(pack_id: str, payload: Optional[Dict[str, Any]] = Body(default=None)) -> Dict[str, Any]:
    return service().save_local_returnables(pack_id, payload)


@router.get("/packs/{pack_id}/submission-binder")
def submission_binder(pack_id: str) -> Dict[str, Any]:
    return service().submission_binder(pack_id)


@router.post("/packs/{pack_id}/submission-binder/generate-local")
def generate_local_submission_binder(pack_id: str) -> Dict[str, Any]:
    return service().generate_local_submission_binder(pack_id)


@router.get("/packs/{pack_id}")
def pack(pack_id: str) -> Dict[str, Any]:
    return service().pack(pack_id)


@router.post("/dry-run")
def dry_run(payload: Optional[Dict[str, Any]] = Body(default=None)) -> Dict[str, Any]:
    return service().dry_run(payload)


@router.post("/generate-local-pack")
def generate_local_pack(payload: Optional[Dict[str, Any]] = Body(default=None)) -> Dict[str, Any]:
    return service().generate_local_pack(payload)
