from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.sbd_version_detector import SBDVersionDetector

router = APIRouter(prefix="/sbd-version", tags=["SBD Version Detector"])


class DetectFileRequest(BaseModel):
    path: str = Field(..., description="Path to a PDF file")


class DetectFolderRequest(BaseModel):
    root_path: str = Field(..., description="Path to a folder containing PDFs")


@router.post("/detect-file")
def detect_file(request: DetectFileRequest):
    try:
        detector = SBDVersionDetector()
        return detector.detect_file(request.path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/detect-folder")
def detect_folder(request: DetectFolderRequest):
    try:
        detector = SBDVersionDetector()
        return detector.detect_folder(request.root_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
