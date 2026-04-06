from __future__ import annotations

# Import model classes so SQLAlchemy registers all tables on Base.metadata.
from app.models import (  # noqa: F401
    AuditLog,
    BuyerEvent,
    BuyerProfile,
    MarkupRule,
    Opportunity,
    ProcurementSignal,
    QuoteDraft,
    QuoteLineItem,
    SubmissionRecord,
    SupplierItem,
    SupplierProduct,
)
