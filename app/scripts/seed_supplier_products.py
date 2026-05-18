# app/scripts/seed_supplier_products.py

from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy.exc import SQLAlchemyError

try:
    from app.db.session import SessionLocal
except Exception:
    try:
        from app.database import SessionLocal
    except Exception as exc:
        raise ImportError(
            "Could not import SessionLocal. Please expose it from app.db.session or app.database."
        ) from exc

from app.models.supplier_product import SupplierProduct

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_data() -> List[Dict[str, Any]]:
    return [
        {
            "supplier_name": "LMCP Preferred Supplier A",
            "product_name": "Business Laptop 15 inch",
            "sku": "IT-LAP-001",
            "unit": "each",
            "category": "IT / Technology",
            "brand": "Generic Business",
            "unit_cost": 12500.00,
            "currency": "ZAR",
            "lead_time_days": 7,
            "min_order_qty": 1,
            "pack_size": "1 unit",
            "supplier_email": "salesA@example.com",
            "supplier_phone": "+27 51 000 0001",
            "province": "Free State",
            "city": "Bloemfontein",
            "is_active": True,
            "is_preferred": True,
            "notes": "Preferred IT supplier",
            "metadata": {
                "keywords": ["laptop", "notebook", "computer", "it equipment"],
            },
        },
        {
            "supplier_name": "LMCP Preferred Supplier B",
            "product_name": "Office Multifunction Printer",
            "sku": "IT-PRN-001",
            "unit": "each",
            "category": "IT / Technology",
            "brand": "Generic Office",
            "unit_cost": 4800.00,
            "currency": "ZAR",
            "lead_time_days": 5,
            "min_order_qty": 1,
            "pack_size": "1 unit",
            "supplier_email": "salesB@example.com",
            "supplier_phone": "+27 51 000 0002",
            "province": "Gauteng",
            "city": "Johannesburg",
            "is_active": True,
            "is_preferred": True,
            "notes": "Printers and office equipment",
            "metadata": {
                "keywords": ["printer", "mfp", "multifunction printer"],
            },
        },
        {
            "supplier_name": "LMCP Preferred Supplier C",
            "product_name": "Stationery Mixed Office Pack",
            "sku": "STA-001",
            "unit": "pack",
            "category": "Office Supplies",
            "brand": "Office General",
            "unit_cost": 950.00,
            "currency": "ZAR",
            "lead_time_days": 3,
            "min_order_qty": 1,
            "pack_size": "bulk office pack",
            "supplier_email": "salesC@example.com",
            "supplier_phone": "+27 51 000 0003",
            "province": "Free State",
            "city": "Bloemfontein",
            "is_active": True,
            "is_preferred": True,
            "notes": "Stationery and consumables",
            "metadata": {
                "keywords": ["stationery", "office supplies", "consumables"],
            },
        },
        {
            "supplier_name": "LMCP Preferred Supplier D",
            "product_name": "Office Desk and Chair Set",
            "sku": "FUR-001",
            "unit": "set",
            "category": "Furniture",
            "brand": "Workspace",
            "unit_cost": 3200.00,
            "currency": "ZAR",
            "lead_time_days": 10,
            "min_order_qty": 1,
            "pack_size": "1 set",
            "supplier_email": "salesD@example.com",
            "supplier_phone": "+27 51 000 0004",
            "province": "KwaZulu-Natal",
            "city": "Durban",
            "is_active": True,
            "is_preferred": False,
            "notes": "Office furniture supplier",
            "metadata": {
                "keywords": ["furniture", "desk", "chair", "office furniture"],
            },
        },
        {
            "supplier_name": "LMCP Preferred Supplier E",
            "product_name": "Protective PPE Kit",
            "sku": "PPE-001",
            "unit": "kit",
            "category": "Apparel / PPE",
            "brand": "SafetyPro",
            "unit_cost": 650.00,
            "currency": "ZAR",
            "lead_time_days": 4,
            "min_order_qty": 5,
            "pack_size": "1 full kit",
            "supplier_email": "salesE@example.com",
            "supplier_phone": "+27 51 000 0005",
            "province": "Western Cape",
            "city": "Cape Town",
            "is_active": True,
            "is_preferred": True,
            "notes": "PPE and protective clothing supplier",
            "metadata": {
                "keywords": ["ppe", "protective equipment", "safety", "uniform"],
            },
        },
        {
            "supplier_name": "LMCP Preferred Supplier F",
            "product_name": "Medical Consumables Bulk Pack",
            "sku": "MED-001",
            "unit": "pack",
            "category": "Medical Supplies",
            "brand": "MediCore",
            "unit_cost": 2400.00,
            "currency": "ZAR",
            "lead_time_days": 6,
            "min_order_qty": 1,
            "pack_size": "bulk consumables",
            "supplier_email": "salesF@example.com",
            "supplier_phone": "+27 51 000 0006",
            "province": "Gauteng",
            "city": "Pretoria",
            "is_active": True,
            "is_preferred": True,
            "notes": "Medical products supplier",
            "metadata": {
                "keywords": ["medical", "medical supplies", "consumables"],
            },
        },
        {
            "supplier_name": "LMCP Preferred Supplier G",
            "product_name": "Cleaning Materials Starter Bundle",
            "sku": "CLN-001",
            "unit": "bundle",
            "category": "Consumables",
            "brand": "CleanPro",
            "unit_cost": 1800.00,
            "currency": "ZAR",
            "lead_time_days": 4,
            "min_order_qty": 1,
            "pack_size": "starter bundle",
            "supplier_email": "salesG@example.com",
            "supplier_phone": "+27 51 000 0007",
            "province": "Free State",
            "city": "Bloemfontein",
            "is_active": True,
            "is_preferred": False,
            "notes": "Cleaning materials supplier",
            "metadata": {
                "keywords": ["cleaning", "cleaning materials", "cleaning supplies"],
            },
        },
        {
            "supplier_name": "LMCP Preferred Supplier H",
            "product_name": "Solar Backup Power Kit",
            "sku": "SOL-001",
            "unit": "kit",
            "category": "Equipment",
            "brand": "EnergyCore",
            "unit_cost": 28500.00,
            "currency": "ZAR",
            "lead_time_days": 14,
            "min_order_qty": 1,
            "pack_size": "complete kit",
            "supplier_email": "salesH@example.com",
            "supplier_phone": "+27 51 000 0008",
            "province": "Northern Cape",
            "city": "Upington",
            "is_active": True,
            "is_preferred": False,
            "notes": "Solar and backup power supplier",
            "metadata": {
                "keywords": ["solar", "inverter", "battery", "backup power"],
            },
        },
    ]


def upsert_supplier_product(db, payload: Dict[str, Any]) -> str:
    supplier_name = payload["supplier_name"]
    product_name = payload["product_name"]
    sku = payload.get("sku")

    existing = (
        db.query(SupplierProduct)
        .filter(
            SupplierProduct.supplier_name == supplier_name,
            SupplierProduct.product_name == product_name,
            SupplierProduct.sku == sku,
        )
        .first()
    )

    if existing:
        existing.update_from_dict(payload)
        return "updated"

    new_item = SupplierProduct(**payload)
    db.add(new_item)
    return "created"


def run_seed() -> Dict[str, Any]:
    db = SessionLocal()
    created = 0
    updated = 0

    try:
        rows = seed_data()

        for payload in rows:
            action = upsert_supplier_product(db, payload)
            if action == "created":
                created += 1
            elif action == "updated":
                updated += 1

        db.commit()

        result = {
            "success": True,
            "created": created,
            "updated": updated,
            "total_processed": len(rows),
        }
        logger.info("Seed completed: %s", result)
        return result

    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while seeding supplier products: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "created": created,
            "updated": updated,
        }

    except Exception as exc:
        db.rollback()
        logger.exception("Unexpected error while seeding supplier products: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "created": created,
            "updated": updated,
        }

    finally:
        db.close()


if __name__ == "__main__":
    output = run_seed()
    print(output)
