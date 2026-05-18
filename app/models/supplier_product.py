# app/models/supplier_product.py

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String, Text

from app.database import Base


class SupplierProduct(Base):
    __tablename__ = "supplier_products"

    id = Column(Integer, primary_key=True, index=True)

    supplier_name = Column(String(255), nullable=False, index=True)
    product_name = Column(String(255), nullable=False, index=True)

    sku = Column(String(100), nullable=True, index=True)
    unit = Column(String(50), nullable=True, default="each")
    category = Column(String(150), nullable=True, index=True)
    brand = Column(String(150), nullable=True, index=True)

    unit_cost = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="ZAR")

    lead_time_days = Column(Integer, nullable=True)
    min_order_qty = Column(Float, nullable=True, default=1.0)
    pack_size = Column(String(100), nullable=True)

    supplier_email = Column(String(255), nullable=True)
    supplier_phone = Column(String(100), nullable=True)

    province = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True, index=True)
    is_preferred = Column(Boolean, nullable=False, default=False, index=True)

    notes = Column(Text, nullable=True)

    # IMPORTANT:
    # SQLAlchemy reserves the attribute name "metadata", so we use
    # "extra_metadata" as the Python attribute while keeping the DB
    # column name as "metadata" for compatibility.
    extra_metadata = Column("metadata", JSON, nullable=True, default=dict)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return (
            f"<SupplierProduct(id={self.id}, supplier_name='{self.supplier_name}', "
            f"product_name='{self.product_name}', sku='{self.sku}')>"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "supplier_name": self.supplier_name,
            "product_name": self.product_name,
            "sku": self.sku,
            "unit": self.unit,
            "category": self.category,
            "brand": self.brand,
            "unit_cost": self.unit_cost,
            "currency": self.currency,
            "lead_time_days": self.lead_time_days,
            "min_order_qty": self.min_order_qty,
            "pack_size": self.pack_size,
            "supplier_email": self.supplier_email,
            "supplier_phone": self.supplier_phone,
            "province": self.province,
            "city": self.city,
            "is_active": self.is_active,
            "is_preferred": self.is_preferred,
            "notes": self.notes,
            "metadata": self.extra_metadata or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def update_from_dict(self, payload: Dict[str, Any]) -> None:
        allowed_fields = {
            "supplier_name",
            "product_name",
            "sku",
            "unit",
            "category",
            "brand",
            "unit_cost",
            "currency",
            "lead_time_days",
            "min_order_qty",
            "pack_size",
            "supplier_email",
            "supplier_phone",
            "province",
            "city",
            "is_active",
            "is_preferred",
            "notes",
        }

        for key, value in payload.items():
            if key in allowed_fields:
                setattr(self, key, value)

        if "metadata" in payload:
            self.extra_metadata = payload.get("metadata") or {}
        if "extra_metadata" in payload:
            self.extra_metadata = payload.get("extra_metadata") or {}
