from fastapi import APIRouter

from app.services.submission_retry_service import retry_failed_submissions

router = APIRouter(prefix="/submission-retry", tags=["submission-retry"])


@router.post("/run")
def run_retry(limit: int = 10):
    return retry_failed_submissions(limit=limit)
