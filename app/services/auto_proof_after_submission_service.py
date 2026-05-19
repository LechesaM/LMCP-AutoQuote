from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)
LEGACY_SERVICE = True


def auto_generate_submission_proof(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate proof PDF immediately after a real submission record is created.

    Defensive by design:
    - Never raises to the pipeline.
    - Returns a structured result.
    - Lets submission continue even if proof generation fails.
    """
    try:
        if not isinstance(record, dict):
            return {
                "status": "skipped",
                "reason": "record_not_dict",
                "proof_generated": False,
            }

        status = str(
            record.get("status")
            or record.get("submission_status")
            or record.get("pipeline_status")
            or ""
        ).lower()

        if status not in {"submitted", "sent", "success", "ok"}:
            return {
                "status": "skipped",
                "reason": f"record_status_not_submitted:{status}",
                "proof_generated": False,
            }

        from app.services.proof_of_submission_service import generate_proof_for_record

        proof_result = generate_proof_for_record(record)

        if isinstance(proof_result, dict):
            return {
                **proof_result,
                "auto_generated": True,
            }

        return {
            "status": "ok",
            "proof_generated": True,
            "auto_generated": True,
            "raw_result": str(proof_result),
        }

    except Exception as exc:
        logger.exception("Auto proof generation failed")
        return {
            "status": "failed",
            "proof_generated": False,
            "auto_generated": True,
            "error": str(exc),
        }
