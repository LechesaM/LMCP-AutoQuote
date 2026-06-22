#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict, Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

RESPONSES_FILE = (
    RUNTIME_DIR
    / "live_supplier_responses"
    / "live_supplier_response_register.json"
)

OUT_DIR = RUNTIME_DIR / "live_supplier_responses"

SELECTION_FILE = OUT_DIR / "best_supplier_selection.json"
AWARD_RECOMMENDATION_FILE = OUT_DIR / "supplier_award_recommendation.json"
SUMMARY_FILE = OUT_DIR / "best_supplier_selection_summary.json"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def money(value):
    try:
        return round(float(value or 0), 2)
    except Exception:
        return 0.0


def clean_key(text):
    return " ".join(str(text or "").lower().split())


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


def main():
    data = load_json(RESPONSES_FILE, default={})
    supplier_responses = data.get("supplier_responses", [])

    grouped = defaultdict(list)

    for supplier_bundle in supplier_responses:
        supplier = supplier_bundle.get("supplier")
        reliability = supplier_bundle.get("supplier_reliability")
        band = supplier_bundle.get("supplier_band")

        for row in supplier_bundle.get("responses", []):
            key = clean_key(row.get("description"))

            grouped[key].append({
                "supplier": supplier,
                "supplier_reliability": reliability,
                "supplier_band": band,
                "description": row.get("description"),
                "category": row.get("category"),
                "original_submission_value": money(row.get("original_submission_value")),
                "supplier_quoted_value": money(row.get("supplier_quoted_value")),
                "achieved_saving": money(row.get("achieved_saving")),
                "saving_pct": money(row.get("saving_pct")),
                "negotiation_outcome": row.get("negotiation_outcome"),
            })

    selected_lines = []
    supplier_awards = defaultdict(lambda: {
        "supplier": None,
        "line_count": 0,
        "award_value": 0.0,
        "original_value": 0.0,
        "saving": 0.0,
        "categories": Counter(),
    })

    for _, quotes in grouped.items():
        quotes = sorted(
            quotes,
            key=lambda x: (
                money(x.get("supplier_quoted_value")),
                -money(x.get("supplier_reliability")),
            ),
        )

        best = quotes[0]
        original = max(money(x.get("original_submission_value")) for x in quotes)
        quoted = money(best.get("supplier_quoted_value"))
        saving = money(original - quoted)

        line = {
            "description": best.get("description"),
            "category": best.get("category"),
            "selected_supplier": best.get("supplier"),
            "selected_supplier_band": best.get("supplier_band"),
            "selected_supplier_reliability": best.get("supplier_reliability"),
            "original_submission_value": original,
            "selected_quote_value": quoted,
            "final_saving": saving,
            "final_saving_pct": round((saving / original) * 100, 2) if original else 0,
            "quotes_received": len(quotes),
            "all_supplier_quotes": quotes,
        }

        selected_lines.append(line)

        supplier = best.get("supplier")
        supplier_awards[supplier]["supplier"] = supplier
        supplier_awards[supplier]["line_count"] += 1
        supplier_awards[supplier]["award_value"] += quoted
        supplier_awards[supplier]["original_value"] += original
        supplier_awards[supplier]["saving"] += saving
        supplier_awards[supplier]["categories"][best.get("category") or "unknown"] += 1

    selected_lines = sorted(
        selected_lines,
        key=lambda x: x["final_saving"],
        reverse=True,
    )

    award_summary = []

    for supplier, row in supplier_awards.items():
        award_summary.append({
            "supplier": supplier,
            "line_count": row["line_count"],
            "award_value": money(row["award_value"]),
            "original_value": money(row["original_value"]),
            "saving": money(row["saving"]),
            "saving_pct": round((row["saving"] / row["original_value"]) * 100, 2)
            if row["original_value"] else 0,
            "category_distribution": dict(row["categories"]),
        })

    award_summary = sorted(
        award_summary,
        key=lambda x: x["award_value"],
        reverse=True,
    )

    total_original = money(sum(x["original_submission_value"] for x in selected_lines))
    total_selected = money(sum(x["selected_quote_value"] for x in selected_lines))
    total_saving = money(total_original - total_selected)

    category_counts = Counter(x["category"] or "unknown" for x in selected_lines)
    supplier_counts = Counter(x["selected_supplier"] for x in selected_lines)

    summary = {
        "generated_at": now_iso(),
        "unique_items_compared": len(selected_lines),
        "total_original_value": total_original,
        "total_best_supplier_value": total_selected,
        "true_saving": total_saving,
        "true_saving_pct": round((total_saving / total_original) * 100, 2)
        if total_original else 0,
        "supplier_award_counts": dict(supplier_counts),
        "category_counts": dict(category_counts),
    }

    write_json(SELECTION_FILE, {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "selected_lines": selected_lines,
    })

    write_json(AWARD_RECOMMENDATION_FILE, {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "supplier_awards": award_summary,
    })

    write_json(SUMMARY_FILE, summary)

    print(f"Best supplier selection written: {SELECTION_FILE}")
    print(f"Supplier award recommendation written: {AWARD_RECOMMENDATION_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Unique items compared: {summary['unique_items_compared']}")
    print(f"Original value: R{summary['total_original_value']:,.2f}")
    print(f"Best supplier value: R{summary['total_best_supplier_value']:,.2f}")
    print(f"True saving: R{summary['true_saving']:,.2f}")
    print(f"True saving pct: {summary['true_saving_pct']}%")


if __name__ == "__main__":
    main()

