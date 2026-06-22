#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = (
    RUNTIME_DIR
    / "supplier_quote_ingestion"
    / "supplier_quote_comparison_matrix.json"
)

OUT_DIR = RUNTIME_DIR / "supplier_quote_adjudication"

AWARD_FILE = OUT_DIR / "award_recommendations.json"
SUMMARY_FILE = OUT_DIR / "adjudication_summary.json"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_json(path, default=None):
    if default is None:
        default = {}

    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def money(value):
    try:
        return round(float(value or 0), 2)
    except Exception:
        return 0.0


def is_priced_quote(q):
    return q.get("unit_price") is not None or q.get("total_price") is not None


def quote_price(q):
    if q.get("total_price") is not None:
        return money(q.get("total_price"))

    qty = money(q.get("quantity") or 1)
    unit = money(q.get("unit_price") or 0)

    return money(qty * unit)


def adjudicate_line(line):
    quotes = line.get("quotes", [])
    priced = [q for q in quotes if is_priced_quote(q)]

    if not priced:
        return {
            "description": line.get("description"),
            "status": "NO_PRICE",
            "recommended_supplier": None,
            "recommended_total": None,
            "quote_count": len(quotes),
            "priced_quote_count": 0,
            "all_quotes": quotes,
        }

    ranked = sorted(priced, key=quote_price)
    best = ranked[0]

    second = ranked[1] if len(ranked) > 1 else None

    best_total = quote_price(best)
    second_total = quote_price(second) if second else None

    saving_vs_second = None
    saving_pct = None

    if second_total is not None and second_total > 0:
        saving_vs_second = money(second_total - best_total)
        saving_pct = round((saving_vs_second / second_total) * 100, 2)

    risk_flags = []

    if len(priced) == 1:
        risk_flags.append("single_quote_only")

    if best_total <= 0:
        risk_flags.append("zero_or_invalid_price")

    if saving_pct is not None and saving_pct > 40:
        risk_flags.append("large_price_gap_review")

    status = "AWARD_RECOMMENDED"

    if risk_flags:
        status = "AWARD_REVIEW"

    return {
        "description": line.get("description"),
        "description_key": line.get("description_key"),
        "status": status,
        "recommended_supplier": best.get("supplier"),
        "recommended_unit_price": best.get("unit_price"),
        "recommended_total": best_total,
        "quantity": best.get("quantity"),
        "unit": best.get("unit"),
        "availability": best.get("availability"),
        "lead_time": best.get("lead_time"),
        "notes": best.get("notes"),
        "quote_count": len(quotes),
        "priced_quote_count": len(priced),
        "second_best_supplier": second.get("supplier") if second else None,
        "second_best_total": second_total,
        "saving_vs_second": saving_vs_second,
        "saving_pct": saving_pct,
        "risk_flags": risk_flags,
        "ranked_quotes": [
            {
                "rank": idx + 1,
                "supplier": q.get("supplier"),
                "unit_price": q.get("unit_price"),
                "total_price": quote_price(q),
                "availability": q.get("availability"),
                "lead_time": q.get("lead_time"),
                "notes": q.get("notes"),
            }
            for idx, q in enumerate(ranked)
        ],
    }


def main():
    data = load_json(INPUT_FILE, default={})
    comparison = data.get("comparison", [])

    recommendations = [adjudicate_line(line) for line in comparison]

    awardable = [
        r for r in recommendations
        if r["status"] in ["AWARD_RECOMMENDED", "AWARD_REVIEW"]
    ]

    no_price = [
        r for r in recommendations
        if r["status"] == "NO_PRICE"
    ]

    supplier_awards = Counter(
        r.get("recommended_supplier")
        for r in awardable
        if r.get("recommended_supplier")
    )

    total_award_value = money(
        sum(money(r.get("recommended_total")) for r in awardable)
    )

    review_count = sum(1 for r in awardable if r["status"] == "AWARD_REVIEW")

    summary = {
        "generated_at": now_iso(),
        "comparison_lines": len(comparison),
        "awardable_lines": len(awardable),
        "no_price_lines": len(no_price),
        "review_lines": review_count,
        "total_award_value": total_award_value,
        "supplier_award_counts": dict(supplier_awards),
    }

    output = {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "recommendations": recommendations,
    }

    write_json(AWARD_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"Adjudication written: {AWARD_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Comparison lines: {summary['comparison_lines']}")
    print(f"Awardable lines: {summary['awardable_lines']}")
    print(f"No price lines: {summary['no_price_lines']}")
    print(f"Review lines: {summary['review_lines']}")
    print(f"Total award value: R{summary['total_award_value']:,.2f}")

    print("\nSupplier award counts:")
    for supplier, count in supplier_awards.most_common():
        print(f"- {supplier}: {count}")


if __name__ == "__main__":
    main()
