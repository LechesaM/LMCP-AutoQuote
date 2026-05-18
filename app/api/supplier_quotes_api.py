from fastapi import APIRouter

from app.services.supplier_quote_ingestion_service import SupplierQuoteIngestionService

router = APIRouter(prefix="/supplier-quotes", tags=["Supplier Quotes"])


@router.get("/status")
def supplier_quotes_status():
    service = SupplierQuoteIngestionService()
    return {
        "enabled": service.enabled,
        "configured": service.is_configured(),
        "imap_host": service.imap_host,
        "email_address": service.email_address,
        "save_root": str(service.save_root),
    }


@router.post("/run-once")
def supplier_quotes_run_once():
    service = SupplierQuoteIngestionService()
    return service.ingest_once()
