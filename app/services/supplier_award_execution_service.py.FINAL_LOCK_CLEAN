from __future__ import annotations

from typing import Any, Dict

from app.services.supplier_quote_award_service import run_full_supplier_quote_cycle
from app.services.supplier_award_document_service import generate_supplier_award_documents


def execute_supplier_award_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    # ================================
    # 🔒 LOCK RFQ + QUOTE (CRITICAL)
    # ================================
    locked_rfq = (
        payload.get("_locked_buyer_rfq_number")
        or payload.get("buyer_rfq_number")
    )

    locked_quote = (
        payload.get("quote_number")
        or (f"LMCP-{locked_rfq}" if locked_rfq else None)
    )

    if locked_rfq:
        payload["_locked_buyer_rfq_number"] = locked_rfq
        payload["buyer_rfq_number"] = locked_rfq
        payload["rfq_number"] = locked_rfq
        payload["reference_number"] = locked_rfq
        payload["document_number"] = locked_rfq

    if locked_quote:
        payload["quote_number"] = locked_quote

    # ================================
    # 🔁 RUN SUPPLIER CYCLE (RESTORE THIS)
    # ================================
    payload = run_full_supplier_quote_cycle(payload)

    # ================================
    # 📄 GENERATE DOCUMENTS
    # ================================
    payload = generate_supplier_award_documents(payload)

    payload["supplier_award_workflow_completed"] = True
    return payload
