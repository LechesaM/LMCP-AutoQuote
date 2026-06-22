#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

SCORECARD_FILE = (
    RUNTIME_DIR
    / "supplier_market_intelligence"
    / "supplier_scorecards.json"
)

QUOTE_INGESTION_FILE = (
    RUNTIME_DIR
    / "supplier_quote_ingestion"
    / "supplier_quote_ingestion_summary.json"
)

OUT_DIR = RUNTIME_DIR / "supplier_market_intelligence"

OUTPUT_FILE = OUT_DIR / "supplier_reliability_v2_scorecards.json"
SUMMARY_FILE = OUT_DIR / "supplier_reliability_v2_summary.json"


SEEDED_DATA_CAP = 65
MIN_REAL_HISTORY_FOR_EXCELLENT = 5


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


def reliability_band(score):
    if score >= 85:
        return "EXCELLENT"
    if score >= 70:
        return "GOOD"
    if score >= 55:
        return "MODERATE"
    if score >= 40:
        return "RISKY"
    return "HIGH_RISK"


def is_seeded_environment(quote_summary):
    return (
        quote_summary.get("quote_files_found", 0) > 0
        and quote_summary.get("priced_items", 0) == quote_summary.get("items_ingested", 0)
        and quote_summary.get("failed_files", []) == []
    )


def adjust_supplier(card, seeded):
    original_score = card.get("reliability_score", 0)
    catalog_items = card.get("catalog_items", 0)
    oem_items = card.get("oem_items", 0)

    adjusted = original_score
    flags = []

    real_response_history = card.get("real_response_history", 0)

    if seeded:
        adjusted = min(adjusted, SEEDED_DATA_CAP)
        flags.append("seeded_quote_data_cap_applied")

    if real_response_history < MIN_REAL_HISTORY_FOR_EXCELLENT:
        adjusted = min(adjusted, 75)
        flags.append("insufficient_real_supplier_history")

    if catalog_items < 50:
        adjusted -= 10
        flags.append("small_catalog_depth")

    if oem_items > 0:
        adjusted += min(10, oem_items)
        flags.append("oem_support_bonus")

    adjusted = max(0, min(100, adjusted))

    out = dict(card)
    out.update({
        "original_reliability_score": original_score,
        "adjusted_reliability_score": adjusted,
        "adjusted_reliability_band": reliability_band(adjusted),
        "real_response_history": real_response_history,
        "reliability_v2_flags": flags,
    })

    return out


def main():
    scorecard_data = load_json(SCORECARD_FILE, default={})
    quote_summary = load_json(QUOTE_INGESTION_FILE, default={})

    cards = scorecard_data.get("supplier_scorecards", [])

    seeded = is_seeded_environment(quote_summary)

    adjusted = [adjust_supplier(card, seeded) for card in cards]

    band_counts = Counter(x["adjusted_reliability_band"] for x in adjusted)

    summary = {
        "generated_at": now_iso(),
        "suppliers_reviewed": len(adjusted),
        "seeded_environment_detected": seeded,
        "adjusted_band_counts": dict(band_counts),
        "top_suppliers": [
            {
                "supplier": x["supplier"],
                "adjusted_score": x["adjusted_reliability_score"],
                "band": x["adjusted_reliability_band"],
                "flags": x["reliability_v2_flags"],
            }
            for x in adjusted
        ],
    }

    write_json(OUTPUT_FILE, {
        "generated_at": summary["generated_at"],
        "supplier_scorecards": adjusted,
    })

    write_json(SUMMARY_FILE, summary)

    print(f"Supplier reliability V2 written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Suppliers reviewed: {summary['suppliers_reviewed']}")
    print(f"Seeded environment detected: {summary['seeded_environment_detected']}")

    print("\nAdjusted supplier bands:")
    for k, v in band_counts.items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
