from app.database import SessionLocal
from app.models import SupplierItem


DEFAULT_ITEMS = [
    {
        "sku": "LMCP-PPE-001",
        "item_name": "Reflective Safety Vest",
        "description": "High-visibility reflective vest",
        "category": "PPE",
        "unit": "each",
        "supplier_name": "LMCP Preferred Supplier",
        "brand": "Generic",
        "default_cost": 65.00,
        "currency": "ZAR",
        "lead_time_days": 3,
        "keywords": "ppe, vest, reflective vest, safety vest, high visibility, uniform",
        "default_quantity": 20,
        "is_active": True,
    },
    {
        "sku": "LMCP-SOLAR-001",
        "item_name": "3kVA Trolley Inverter",
        "description": "Portable trolley inverter unit",
        "category": "Solar",
        "unit": "each",
        "supplier_name": "LMCP Preferred Supplier",
        "brand": "Generic",
        "default_cost": 5200.00,
        "currency": "ZAR",
        "lead_time_days": 7,
        "keywords": "inverter, trolley inverter, backup power, solar, ups, 3kva",
        "default_quantity": 5,
        "is_active": True,
    },
    {
        "sku": "LMCP-ELEC-001",
        "item_name": "LED Floodlight 200W",
        "description": "Outdoor LED floodlight",
        "category": "Electrical",
        "unit": "each",
        "supplier_name": "LMCP Preferred Supplier",
        "brand": "Generic",
        "default_cost": 1450.00,
        "currency": "ZAR",
        "lead_time_days": 5,
        "keywords": "floodlight, led, outdoor lighting, lighting, electrical",
        "default_quantity": 10,
        "is_active": True,
    },
    {
        "sku": "LMCP-WATER-001",
        "item_name": "HDPE Pipe 110mm",
        "description": "110mm HDPE pipe for water reticulation",
        "category": "Water",
        "unit": "m",
        "supplier_name": "LMCP Preferred Supplier",
        "brand": "Generic",
        "default_cost": 185.00,
        "currency": "ZAR",
        "lead_time_days": 10,
        "keywords": "hdpe, pipe, water reticulation, water pipe, 110mm, pipeline",
        "default_quantity": 100,
        "is_active": True,
    },
    {
        "sku": "LMCP-ROAD-001",
        "item_name": "Road Sign Assembly",
        "description": "Complete road sign assembly with pole",
        "category": "Road Signs",
        "unit": "each",
        "supplier_name": "LMCP Preferred Supplier",
        "brand": "Generic",
        "default_cost": 2800.00,
        "currency": "ZAR",
        "lead_time_days": 14,
        "keywords": "road sign, sign assembly, sign pole, traffic sign, road signs",
        "default_quantity": 8,
        "is_active": True,
    },
    {
        "sku": "LMCP-OFFICE-001",
        "item_name": "Office Chair",
        "description": "Ergonomic office chair",
        "category": "Furniture",
        "unit": "each",
        "supplier_name": "LMCP Preferred Supplier",
        "brand": "Generic",
        "default_cost": 1350.00,
        "currency": "ZAR",
        "lead_time_days": 7,
        "keywords": "chair, office chair, furniture, seating",
        "default_quantity": 10,
        "is_active": True,
    },
    {
        "sku": "LMCP-IT-001",
        "item_name": "Laptop Computer",
        "description": "Business-use laptop computer",
        "category": "IT Equipment",
        "unit": "each",
        "supplier_name": "LMCP Preferred Supplier",
        "brand": "Generic",
        "default_cost": 9500.00,
        "currency": "ZAR",
        "lead_time_days": 7,
        "keywords": "laptop, notebook, computer, it equipment",
        "default_quantity": 5,
        "is_active": True,
    },
    {
        "sku": "LMCP-PRINT-001",
        "item_name": "Multifunction Printer",
        "description": "Office multifunction printer",
        "category": "IT Equipment",
        "unit": "each",
        "supplier_name": "LMCP Preferred Supplier",
        "brand": "Generic",
        "default_cost": 4200.00,
        "currency": "ZAR",
        "lead_time_days": 5,
        "keywords": "printer, multifunction printer, office printer, printing",
        "default_quantity": 2,
        "is_active": True,
    },
]


def run():
    db = SessionLocal()
    try:
        added = 0
        for item in DEFAULT_ITEMS:
            exists = db.query(SupplierItem).filter(SupplierItem.sku == item["sku"]).first()
            if exists:
                continue
            db.add(SupplierItem(**item))
            added += 1
        db.commit()
        print({"status": "ok", "added": added})
    finally:
        db.close()


if __name__ == "__main__":
    run()
