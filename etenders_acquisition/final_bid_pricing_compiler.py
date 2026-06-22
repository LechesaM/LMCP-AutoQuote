#!/usr/bin/env python3
import csv
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = RUNTIME_DIR / "rate_sanity" / "rate_sanitized_estimates.json"

OUT_DIR = RUNTIME_DIR / "final_bid_pricing"

JSON_FILE = OUT_DIR / "final_bid_pricing_schedule.json"
CSV_FILE = OUT_DIR / "final_bid_pricing_schedule.csv"
SUMMARY_FILE = OUT_DIR / "final_bid_pricing_summary.json"

DEFAULT_MARGIN = 0.22

MARGIN_BY_CONFIDENCE = {
    "HIGH": 0.18,
    "SKU_HIGH": 0.18,
    "MEDIUM": 0.24,
    "LOW": 0.28,
    "FALLBACK_LOW": 0.32,
    "NO_MATCH": 0.40,
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def money(v):
    try:
        return round(float(v or 0), 2)
    except Exception:
        return 0.0


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


def margin_for(item):
    confidence = item.get("confidence") or "NO_MATCH"
    return MARGIN_BY_CONFIDENCE.get(confidence, DEFAULT_MARGIN)


def compile_line(item, line_no):
    cost_total = money(item.get("adjusted_total"))
    quantity = money(item.get("quantity") or 1)
    cost_unit = money(item.get("adjusted_unit_price"))

    margin = margin_for(item)
    sell_unit = money(cost_unit * (1 + margin))
    sell_total = money(sell_unit * quantity)
    profit = money(sell_total - cost_total)

    return {
        "line_no": line_no,
        "description": item.get("description"),
        "category": item.get("category"),
        "quantity": quantity,
        "unit": item.get("unit"),
        "source_confidence": item.get("confidence"),
        "estimate_status": item.get("estimate_status"),
        "supplier": item.get("matched_supplier"),
        "cost_unit_rate": cost_unit,
        "cost_total": cost_total,
        "margin_pct": round(margin * 100, 2),
        "bid_unit_rate": sell_unit,
        "bid_total": sell_total,
        "gross_profit": profit,
        "rate_sanity_status": item.get("rate_sanity_status"),
        "rate_sanity_flags": item.get("rate_sanity_flags", []),
        "pricing_source": item.get("pricing_source"),
    }


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "line_no",
        "description",
        "category",
        "quantity",
        "unit",
        "source_confidence",
        "estimate_status",
        "supplier",
        "cost_unit_rate",
        "cost_total",
        "margin_pct",
        "bid_unit_rate",
        "bid_total",
        "gross_profit",
        "rate_sanity_status",
        "rate_sanity_flags",
        "pricing_source",
    ]

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for row in rows:
            r = dict(row)
            r["rate_sanity_flags"] = ",".join(r.get("rate_sanity_flags") or [])
            writer.writerow(r)


def main():
    data = load_json(INPUT_FILE, default={})
    items = data.get("items", [])

    lines = [
        compile_line(item, idx)
        for idx, item in enumerate(items, start=1)
    ]

    total_cost = money(sum(x["cost_total"] for x in lines))
    total_bid = money(sum(x["bid_total"] for x in lines))
    total_profit = money(sum(x["gross_profit"] for x in lines))

    avg_margin = round((total_profit / total_cost) * 100, 2) if total_cost else 0

    confidence_counts = Counter(x["source_confidence"] for x in lines)
    category_counts = Counter(x["category"] or "unknown" for x in lines)
    estimate_status_counts = Counter(x["estimate_status"] for x in lines)
    sanity_counts = Counter(x["rate_sanity_status"] for x in lines)

    summary = {
        "generated_at": now_iso(),
        "total_lines": len(lines),
        "total_cost_value": total_cost,
        "total_bid_value": total_bid,
        "total_gross_profit": total_profit,
        "average_margin_pct": avg_margin,
        "confidence_counts": dict(confidence_counts),
        "category_counts": dict(category_counts),
        "estimate_status_counts": dict(estimate_status_counts),
        "rate_sanity_counts": dict(sanity_counts),
        "csv_file": str(CSV_FILE),
        "json_file": str(JSON_FILE),
    }

    output = {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "pricing_schedule": lines,
    }

    write_json(JSON_FILE, output)
    write_json(SUMMARY_FILE, summary)
    write_csv(CSV_FILE, lines)

    print(f"Final bid pricing JSON written: {JSON_FILE}")
    print(f"Final bid pricing CSV written: {CSV_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Lines: {summary['total_lines']}")
    print(f"Cost value: R{summary['total_cost_value']:,.2f}")
    print(f"Bid value: R{summary['total_bid_value']:,.2f}")
    print(f"Gross profit: R{summary['total_gross_profit']:,.2f}")
    print(f"Average margin: {summary['average_margin_pct']}%")


if __name__ == "__main__":
    main()
