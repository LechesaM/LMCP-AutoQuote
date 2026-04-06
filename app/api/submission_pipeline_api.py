from fastapi import APIRouter
from app.services.submission_pipeline import SubmissionPipeline

router = APIRouter(prefix="/submission-pipeline", tags=["Submission Pipeline"])


@router.post("/run")
def run_pipeline():
    return SubmissionPipeline.run()
