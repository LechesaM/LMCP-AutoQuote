from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.submission_history_proof_enrichment_service import (
    enrich_submission_history_with_proof_paths,
    get_submission_history_with_proofs,
)

router = APIRouter(
    prefix="/submission-history",
    tags=["Submission History Proofs"],
)


@router.post("/proof-sync")
def sync_proof_paths():
    return enrich_submission_history_with_proof_paths()


@router.get("/recent-with-proofs")
def recent_with_proofs(limit: int = Query(default=20, ge=1, le=100)):
    return get_submission_history_with_proofs(limit=limit)
