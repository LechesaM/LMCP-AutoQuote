from fastapi import APIRouter
from app.services.supplier_quote_ingestion_service import ingest_supplier_quotes

router = APIRouter(prefix="/email", tags=["Email Ingestion"])


@router.post("/ingest-supplier-quotes")
def run_supplier_ingestion():
    result = ingest_supplier_quotes()
    return {
        "status": "success",
        "message": "Supplier ingestion completed",
        "data": result,
    }
