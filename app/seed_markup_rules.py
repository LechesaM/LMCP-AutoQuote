from app.database import SessionLocal
from app.models import MarkupRule


DEFAULT_RULES = [
    {
        "name": "FS high-score premium",
        "description": "Free State opportunities with strong score",
        "min_score": 75,
        "max_score": None,
        "min_estimated_value": None,
        "max_estimated_value": None,
        "province": "Free State",
        "buyer_name_contains": None,
        "category_contains": None,
        "markup_pct": 24.0,
        "priority": 1,
        "is_active": True,
    },
    {
        "name": "SANRAL strategic supply",
        "description": "Strategic SANRAL supply opportunities",
        "min_score": 65,
        "max_score": None,
        "min_estimated_value": None,
        "max_estimated_value": None,
        "province": None,
        "buyer_name_contains": "sanral",
        "category_contains": None,
        "markup_pct": 20.0,
        "priority": 2,
        "is_active": True,
    },
    {
        "name": "Small quick-win supplies",
        "description": "Small value quick turnaround supply opportunities",
        "min_score": 50,
        "max_score": None,
        "min_estimated_value": None,
        "max_estimated_value": None,
        "province": None,
        "buyer_name_contains": None,
        "category_contains": "supply",
        "markup_pct": 26.0,
        "priority": 3,
        "is_active": True,
    },
]


def run():
    db = SessionLocal()
    try:
        for item in DEFAULT_RULES:
            exists = db.query(MarkupRule).filter(MarkupRule.name == item["name"]).first()
            if exists:
                continue

            rule = MarkupRule(**item)
            db.add(rule)

        db.commit()
        print({"status": "ok", "seeded_rules": len(DEFAULT_RULES)})
    finally:
        db.close()


if __name__ == "__main__":
    run()
