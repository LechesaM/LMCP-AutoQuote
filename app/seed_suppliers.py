from datetime import datetime

from app.database import SessionLocal
from app.models import SupplierItem


def seed_suppliers():

    db = SessionLocal()

    items = [

        {
            "supplier_name": "Ingram Micro SA",
            "description": "Laptop Computer",
            "category": "IT Equipment",
            "unit_price": 8500,
        },

        {
            "supplier_name": "Rectron",
            "description": "Laser Printer",
            "category": "IT Equipment",
            "unit_price": 3200,
        },

        {
            "supplier_name": "Mustek",
            "description": "Desktop Computer",
            "category": "IT Equipment",
            "unit_price": 7200,
        },

        {
            "supplier_name": "Office National",
            "description": "Office Chair",
            "category": "Furniture",
            "unit_price": 950,
        },

        {
            "supplier_name": "Makro Supplier",
            "description": "Office Desk",
            "category": "Furniture",
            "unit_price": 1800,
        },

        {
            "supplier_name": "Solar Warehouse",
            "description": "3kVA Solar Inverter",
            "category": "Energy Equipment",
            "unit_price": 6800,
        },

        {
            "supplier_name": "JoJo Tanks",
            "description": "5000L Water Tank",
            "category": "Water Equipment",
            "unit_price": 2400,
        },

        {
            "supplier_name": "Builders Warehouse",
            "description": "PVC Pipes",
            "category": "Construction Materials",
            "unit_price": 120,
        },

        {
            "supplier_name": "Takealot Business",
            "description": "Wireless Router",
            "category": "Networking Equipment",
            "unit_price": 650,
        },

        {
            "supplier_name": "Game Supplier",
            "description": "Stationery Pack",
            "category": "Office Supplies",
            "unit_price": 180,
        },

    ]

    for item in items:

        exists = db.query(SupplierItem).filter(
            SupplierItem.description == item["description"]
        ).first()

        if exists:
            continue

        supplier_item = SupplierItem(
            supplier_name=item["supplier_name"],
            description=item["description"],
            category=item["category"],
            unit_price=item["unit_price"],
            created_at=datetime.utcnow()
        )

        db.add(supplier_item)

    db.commit()
    db.close()

    print("Supplier catalogue seeded successfully.")


if __name__ == "__main__":
    seed_suppliers()
