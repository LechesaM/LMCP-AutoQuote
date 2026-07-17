from fastapi import APIRouter

from app.services.supplier_quote_ingestion_service import SupplierQuoteIngestionService

router = APIRouter(prefix="/supplier-quotes", tags=["Supplier Quotes"])


@router.get("/status")
def supplier_quotes_status():
    service = SupplierQuoteIngestionService()
    return service.status()


@router.post("/run-once")
def supplier_quotes_run_once():
    service = SupplierQuoteIngestionService()
    return service.ingest_once()
