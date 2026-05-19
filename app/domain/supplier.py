from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.domain.base import StrictBaseModel


class SupplierQuoteLine(StrictBaseModel):
    description: str
    quantity: float = 0.0
    unit_price: float = 0.0
    delivery_cost: float = 0.0
    vat_amount: float = 0.0
    available: bool = True
    notes: List[str] = Field(default_factory=list)

class SupplierRecord(StrictBaseModel):
    supplier_name: str
    contact_name: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    vat_registered: bool = False
    notes: List[str] = Field(default_factory=list)


class SupplierQuote(StrictBaseModel):
    supplier: SupplierRecord
    quote_reference: str = ""
    quote_valid_until: Optional[datetime] = None
    confidence_notes: List[str] = Field(default_factory=list)
    lines: List[SupplierQuoteLine] = Field(default_factory=list)
    confidence_score: float = 0.0
    price_anomaly_notes: List[str] = Field(default_factory=list)
    comparison_summary: Dict[str, Any] = Field(default_factory=dict)
