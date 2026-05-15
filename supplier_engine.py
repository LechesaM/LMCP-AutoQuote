from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


SUPPLIER_DATA_FILE = os.getenv(
    "LMCP_SUPPLIER_DATA_FILE",
    "runtime/suppliers_master.json"
)


EXCLUDED_SUPPLIER_CATEGORIES = {
    "medical_consumables",
    "it_equipment",
    "petrol_diesel_supply",
}


@dataclass
class SupplierProduct:
    product_name: str
    category: str
    unit_price: float
    unit: str = "each"
    lead_time_days: int = 3
    available_stock: int = 0


@dataclass
class SupplierRecord:
    supplier_id: str
    supplier_name: str
    province: str
    city: str
    contact_person: str
    email: str
    phone: str
    delivery_regions: List[str]
    products: List[SupplierProduct]


DEFAULT_SUPPLIERS: List[SupplierRecord] = [
    SupplierRecord(
        supplier_id="SUP-001",
        supplier_name="LMCP Industrial Supplies",
        province="Free State",
        city="Bloemfontein",
        contact_person="Sales Desk",
        email="sales@lmcp-industrial.example",
        phone="+27-51-000-0001",
        delivery_regions=["Free State", "Northern Cape", "Eastern Cape", "Gauteng"],
        products=[
            SupplierProduct("HDPE pipe", "plumbing_water", 850.00, "length", 4, 5000),
            SupplierProduct("Valve", "plumbing_water", 450.00, "each", 3, 2500),
            SupplierProduct("Safety gloves", "ppe", 35.00, "pair", 2, 25000),
            SupplierProduct("Reflective vest", "ppe", 55.00, "each", 2, 12000),
            SupplierProduct("A4 paper", "stationery_office", 75.00, "ream", 2, 18000),
            SupplierProduct("Cement", "building_materials", 120.00, "bag", 2, 40000),
            SupplierProduct("Paint", "building_materials", 480.00, "bucket", 2, 5000),
            SupplierProduct("Brick", "building_materials", 4.50, "each", 3, 250000),
            SupplierProduct("Sand", "building_materials", 650.00, "m3", 2, 5000),
        ],
    ),
    SupplierRecord(
        supplier_id="SUP-002",
        supplier_name="National Office & Hygiene Distributors",
        province="Gauteng",
        city="Johannesburg",
        contact_person="Bid Desk",
        email="bids@noh-distributors.example",
        phone="+27-11-000-0002",
        delivery_regions=["All"],
        products=[
            SupplierProduct("A4 paper", "stationery_office", 72.00, "ream", 2, 30000),
            SupplierProduct("Toner cartridge", "stationery_office", 950.00, "each", 3, 1200),
            SupplierProduct("Lever arch file", "stationery_office", 38.00, "each", 2, 20000),
            SupplierProduct("Disinfectant", "cleaning_hygiene", 120.00, "bottle", 2, 20000),
            SupplierProduct("Toilet paper", "cleaning_hygiene", 85.00, "pack", 2, 30000),
            SupplierProduct("Mop", "cleaning_hygiene", 65.00, "each", 2, 8000),
            SupplierProduct("Filing cabinet", "furniture", 2400.00, "each", 4, 600),
            SupplierProduct("Office chair", "furniture", 1800.00, "each", 4, 1200),
            SupplierProduct("Desk", "furniture", 3200.00, "each", 5, 900),
        ],
    ),
    SupplierRecord(
        supplier_id="SUP-003",
        supplier_name="ElectroBuild Bulk Traders",
        province="KwaZulu-Natal",
        city="Durban",
        contact_person="Corporate Sales",
        email="quotes@electrobuild.example",
        phone="+27-31-000-0003",
        delivery_regions=["All"],
        products=[
            SupplierProduct("Cable", "electrical", 1200.00, "roll", 5, 3000),
            SupplierProduct("Light fitting", "electrical", 340.00, "each", 4, 7000),
            SupplierProduct("Distribution board", "electrical", 2100.00, "each", 5, 850),
            SupplierProduct("Conduit", "electrical", 160.00, "length", 4, 10000),
            SupplierProduct("Socket outlet", "electrical", 85.00, "each", 3, 12000),
            SupplierProduct("Circuit breaker", "electrical", 240.00, "each", 4, 6000),
        ],
    ),
    SupplierRecord(
        supplier_id="SUP-004",
        supplier_name="Agri Water and Safety Wholesale",
        province="Western Cape",
        city="Cape Town",
        contact_person="Public Sector Sales",
        email="tenders@agriwatersafety.example",
        phone="+27-21-000-0004",
        delivery_regions=["All"],
        products=[
            SupplierProduct("Fertilizer", "agriculture_inputs", 420.00, "bag", 4, 12000),
            SupplierProduct("Seed", "agriculture_inputs", 180.00, "pack", 3, 15000),
            SupplierProduct("Animal feed", "agriculture_inputs", 390.00, "bag", 4, 10000),
            SupplierProduct("Fire extinguisher", "safety_security_general", 850.00, "each", 3, 4000),
            SupplierProduct("Road sign", "safety_security_general", 1450.00, "each", 5, 3000),
            SupplierProduct("Safety signage", "safety_security_general", 280.00, "each", 3, 5000),
            SupplierProduct("Chlorine", "water_treatment_chemicals", 390.00, "drum", 4, 2000),
            SupplierProduct("Alum", "water_treatment_chemicals", 310.00, "bag", 4, 3500),
        ],
    ),
]


def _ensure_runtime_dir() -> None:
    os.makedirs(os.path.dirname(SUPPLIER_DATA_FILE), exist_ok=True)


def _save_default_suppliers() -> None:
    _ensure_runtime_dir()
    payload = [asdict(supplier) for supplier in DEFAULT_SUPPLIERS]

    with open(SUPPLIER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _load_suppliers() -> List[SupplierRecord]:
    if not os.path.exists(SUPPLIER_DATA_FILE):
        _save_default_suppliers()

    with open(SUPPLIER_DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    suppliers: List[SupplierRecord] = []
    for item in data:
        products = [SupplierProduct(**p) for p in item.get("products", [])]
        products = [p for p in products if p.category not in EXCLUDED_SUPPLIER_CATEGORIES]

        supplier = SupplierRecord(
            supplier_id=item["supplier_id"],
            supplier_name=item["supplier_name"],
            province=item["province"],
            city=item["city"],
            contact_person=item["contact_person"],
            email=item["email"],
            phone=item["phone"],
            delivery_regions=item.get("delivery_regions", []),
            products=products,
        )
        suppliers.append(supplier)

    return suppliers


def get_all_suppliers() -> List[Dict[str, Any]]:
    return [asdict(s) for s in _load_suppliers()]


def _region_supported(delivery_regions: List[str], destination: Optional[str]) -> bool:
    if not delivery_regions:
        return True
    if "All" in delivery_regions:
        return True
    if not destination:
        return True

    destination_lower = destination.lower()
    return any(region.lower() in destination_lower for region in delivery_regions)


def find_supplier_options(
    category: str,
    delivery_location: Optional[str] = None,
    min_stock: int = 1,
) -> List[Dict[str, Any]]:
    if category in EXCLUDED_SUPPLIER_CATEGORIES:
        return []

    suppliers = _load_suppliers()
    matches: List[Dict[str, Any]] = []

    for supplier in suppliers:
        if not _region_supported(supplier.delivery_regions, delivery_location):
            continue

        for product in supplier.products:
            if product.category != category:
                continue
            if product.available_stock < min_stock:
                continue

            matches.append({
                "supplier_id": supplier.supplier_id,
                "supplier_name": supplier.supplier_name,
                "province": supplier.province,
                "city": supplier.city,
                "contact_person": supplier.contact_person,
                "email": supplier.email,
                "phone": supplier.phone,
                "delivery_regions": supplier.delivery_regions,
                "product_name": product.product_name,
                "category": product.category,
                "unit_price": product.unit_price,
                "unit": product.unit,
                "lead_time_days": product.lead_time_days,
                "available_stock": product.available_stock,
            })

    matches.sort(
        key=lambda x: (
            x["unit_price"],
            x["lead_time_days"],
            -x["available_stock"],
        )
    )
    return matches


def choose_best_supplier(
    category: str,
    delivery_location: Optional[str] = None,
    min_stock: int = 1,
) -> Optional[Dict[str, Any]]:
    options = find_supplier_options(
        category=category,
        delivery_location=delivery_location,
        min_stock=min_stock,
    )
    if not options:
        return None
    return options[0]
