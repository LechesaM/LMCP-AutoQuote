from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def generate_auto_proof_after_submission(record: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if not isinstance(record, dict):
            return {"status": "skipped", "proof_generated": False, "reason": "record_not_dict"}

        status = str(
            record.get("submission_status")
            or record.get("pipeline_status")
            or record.get("status")
            or ""
        ).strip().lower()

        if status not in {"submitted", "sent", "success", "ok"}:
            return {"status": "skipped", "proof_generated": False, "reason": f"not_submitted:{status}"}

        try:
            from app.services.proof_of_submission_service import generate_proof_for_record
        except Exception as import_exc:
            return {
                "status": "failed",
                "proof_generated": False,
                "reason": "proof_service_import_failed",
                "error": str(import_exc),
            }

        proof_result = generate_proof_for_record(record)
        if not isinstance(proof_result, dict):
            proof_result = {"status": "ok", "proof_generated": True, "raw_result": str(proof_result)}

        proof_result["auto_generated"] = True
        return proof_result

    except Exception as exc:
        logger.exception("Auto proof after submission failed")
        return {"status": "failed", "proof_generated": False, "auto_generated": True, "error": str(exc)}


def attach_auto_proof_to_result(result: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(result or {})
    submission_pack = payload.get("submission_pack")

    if isinstance(submission_pack, dict):
        record = {**payload, **submission_pack}
    else:
        record = payload

    proof = generate_auto_proof_after_submission(record)
    payload["auto_proof_result"] = proof

    if isinstance(proof, dict):
        proof_pdf_path = proof.get("proof_pdf_path")
        if proof_pdf_path:
            payload["proof_pdf_path"] = proof_pdf_path
            payload["proof_url"] = "/" + str(proof_pdf_path).lstrip("/")

        if isinstance(submission_pack, dict):
            submission_pack["auto_proof_result"] = proof
            if proof_pdf_path:
                submission_pack["proof_pdf_path"] = proof_pdf_path
                submission_pack["proof_url"] = "/" + str(proof_pdf_path).lstrip("/")
            payload["submission_pack"] = submission_pack

    return payload
