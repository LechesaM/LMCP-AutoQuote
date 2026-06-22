#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

MANUAL_PRODUCTION_DIR = RUNTIME_DIR / "manual_production"
REVIEW_QUARANTINE_DIR = RUNTIME_DIR / "review_quarantine"

QUOTE_PACK_INDEX_FILE = MANUAL_PRODUCTION_DIR / "quote_pack_index.json"
QUARANTINE_SUMMARY_FILE = REVIEW_QUARANTINE_DIR / "review_item_quarantine_summary.json"

SUPPLY_RFQ_FILE = RUNTIME_DIR / "portal_fetch" / "logs" / "supply_delivery_rfqs.json"
SUPPLY_PACK_INDEX_FILE = (
    MANUAL_PRODUCTION_DIR
    / "supply_delivery_quote_packs"
    / "supply_delivery_quote_pack_index.json"
)

AJAX_FEED_SUMMARY_FILE = RUNTIME_DIR / "ajax_tender_feed" / "ajax_tender_feed_summary.json"
AJAX_SUPPLY_PACK_INDEX_FILE = (
    MANUAL_PRODUCTION_DIR
    / "ajax_supply_quote_packs"
    / "ajax_supply_quote_pack_index.json"
)

BOQ_SUMMARY_FILE = RUNTIME_DIR / "boq_intelligence" / "deduplicated_boq_summary.json"
PRICING_SUMMARY_FILE = RUNTIME_DIR / "pricing_engine" / "pricing_candidates_summary.json"
SUPPLIER_MATCH_SUMMARY_FILE = RUNTIME_DIR / "supplier_matching" / "supplier_match_summary.json"
RFQ_PACK_SUMMARY_FILE = RUNTIME_DIR / "rfq_packs" / "rfq_pack_summary.json"

OUTPUT_FILE = MANUAL_PRODUCTION_DIR / "quote_pack_dashboard_metrics.json"


def load_json(path, default=None):
    if default is None:
        default = {}

    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_packs(index_data):
    if isinstance(index_data, list):
        return index_data

    if not isinstance(index_data, dict):
        return []

    for key in ["quote_packs", "packs", "items", "quote_pack_index", "data", "results"]:
        value = index_data.get(key)
        if isinstance(value, list):
            return value

    return []


def is_priced(pack):
    return bool(
        pack.get("pricing_attached")
        or pack.get("has_pricing")
        or pack.get("priced")
        or pack.get("pricing_summary_file")
        or pack.get("pricing_summary_path")
        or pack.get("pricing")
    )


def requires_review(pack):
    flags = pack.get("serious_flags") or pack.get("flags") or []

    return bool(
        pack.get("requires_manual_review")
        or pack.get("review_required")
        or pack.get("status") == "REVIEW_REQUIRED"
        or pack.get("pricing_status") == "REVIEW_REQUIRED"
        or "high_tender_total" in flags
        or "high_item_total" in flags
    )


def main():
    index_data = load_json(QUOTE_PACK_INDEX_FILE, default={})
    quarantine_summary = load_json(QUARANTINE_SUMMARY_FILE, default={})

    supply_rfqs = load_json(SUPPLY_RFQ_FILE, default={})
    supply_pack_index = load_json(SUPPLY_PACK_INDEX_FILE, default={})

    ajax_feed_summary = load_json(AJAX_FEED_SUMMARY_FILE, default={})
    ajax_supply_pack_index = load_json(AJAX_SUPPLY_PACK_INDEX_FILE, default={})

    boq_summary = load_json(BOQ_SUMMARY_FILE, default={})
    pricing_summary = load_json(PRICING_SUMMARY_FILE, default={})
    supplier_match_summary = load_json(SUPPLIER_MATCH_SUMMARY_FILE, default={})
    rfq_pack_summary = load_json(RFQ_PACK_SUMMARY_FILE, default={})

    packs = extract_packs(index_data)

    total_packs = len(packs)
    priced_packs = 0
    missing_pricing = 0
    review_required = 0
    ready_without_flags = 0

    for pack in packs:
        if not isinstance(pack, dict):
            continue

        priced = is_priced(pack)
        review = requires_review(pack)

        if priced:
            priced_packs += 1
        else:
            missing_pricing += 1

        if review:
            review_required += 1

        if priced and not review:
            ready_without_flags += 1

    quarantined_tenders = int(quarantine_summary.get("quarantined_tenders") or 0)
    quarantined_tender_ids = quarantine_summary.get("quarantined_tender_ids") or []

    if quarantined_tenders > review_required:
        review_required = quarantined_tenders

    supply_packs = supply_pack_index.get("packs", [])
    supply_awaiting = [
        p for p in supply_packs
        if p.get("pricing_status") == "AWAITING_DOCUMENTS_OR_SUPPLIER_PRICING"
    ]

    ajax_supply_packs = ajax_supply_pack_index.get("packs", [])

    dashboard = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "READY" if ready_without_flags > 0 else "REVIEW_REQUIRED",

        "quote_pack_summary": {
            "total_quote_packs": total_packs,
            "priced_quote_packs": priced_packs,
            "missing_pricing": missing_pricing,
            "review_required": review_required,
            "ready_without_flags": ready_without_flags,
        },

        "review_quarantine": {
            "quarantined_tenders": quarantined_tenders,
            "quarantined_tender_ids": quarantined_tender_ids,
        },

        "supply_delivery_pipeline": {
            "rows_seen": supply_rfqs.get("total_rows_seen", 0),
            "accepted_rfqs": supply_rfqs.get("accepted_supply_delivery", 0),
            "review_mixed": supply_rfqs.get("review_mixed", 0),
            "rejected_not_supply_delivery": supply_rfqs.get(
                "rejected_not_supply_delivery", 0
            ),
            "quote_packs_generated": supply_pack_index.get(
                "total_supply_delivery_quote_packs",
                len(supply_packs),
            ),
            "awaiting_documents_or_supplier_pricing": len(supply_awaiting),
        },

        "ajax_supply_pipeline": {
            "live_tenders_harvested": ajax_feed_summary.get("rows_fetched", 0),
            "records_total": ajax_feed_summary.get("records_total", 0),
            "accepted_supply_delivery": ajax_feed_summary.get(
                "accepted_supply_delivery", 0
            ),
            "review_mixed": ajax_feed_summary.get("review_mixed", 0),
            "rejected": ajax_feed_summary.get("rejected", 0),
            "support_documents_total": ajax_feed_summary.get(
                "support_documents_total", 0
            ),
            "accepted_support_documents": ajax_feed_summary.get(
                "accepted_support_documents", 0
            ),
            "quote_packs_generated": ajax_supply_pack_index.get(
                "total_ajax_supply_quote_packs",
                len(ajax_supply_packs),
            ),
        },

        "boq_intelligence_pipeline": {
            "input_usable_items": boq_summary.get("input_usable_items", 0),
            "deduplicated_items": boq_summary.get("deduplicated_items", 0),
            "usable_for_pricing": boq_summary.get("usable_for_pricing", 0),
            "review_items": boq_summary.get("review_items", 0),
            "duplicate_groups": boq_summary.get("duplicate_groups", 0),
            "confidence_counts": boq_summary.get("confidence_counts", {}),
            "category_counts": boq_summary.get("category_counts", {}),
        },

        "pricing_intelligence_pipeline": {
            "pricing_candidates": pricing_summary.get("pricing_candidates", 0),
            "product_type_counts": pricing_summary.get("product_type_counts", {}),
            "pricing_confidence_counts": pricing_summary.get(
                "pricing_confidence_counts", {}
            ),
            "category_counts": pricing_summary.get("category_counts", {}),
        },

        "supplier_matching_pipeline": {
            "matched_items": supplier_match_summary.get("matched_items", 0),
            "supplier_counts": supplier_match_summary.get("supplier_counts", {}),
            "confidence_counts": supplier_match_summary.get("confidence_counts", {}),
        },

        "rfq_pack_pipeline": {
            "total_rfq_packs": rfq_pack_summary.get("total_rfq_packs", 0),
            "total_items": rfq_pack_summary.get("total_items", 0),
            "total_estimated_value": rfq_pack_summary.get(
                "total_estimated_value", 0
            ),
            "suppliers": rfq_pack_summary.get("suppliers", []),
        },
    }

    write_json(OUTPUT_FILE, dashboard)

    print(f"Quote pack dashboard metrics generated: {OUTPUT_FILE}")
    print(f"Status: {dashboard['status']}")
    print(f"Total packs: {total_packs}")
    print(f"Priced packs: {priced_packs}")
    print(f"Missing pricing: {missing_pricing}")
    print(f"Review required: {review_required}")
    print(f"Ready without flags: {ready_without_flags}")
    print(
        "AJAX accepted supply/delivery: "
        f"{dashboard['ajax_supply_pipeline']['accepted_supply_delivery']}"
    )
    print(
        "BOQ usable for pricing: "
        f"{dashboard['boq_intelligence_pipeline']['usable_for_pricing']}"
    )
    print(
        "Pricing candidates: "
        f"{dashboard['pricing_intelligence_pipeline']['pricing_candidates']}"
    )
    print(
        "Supplier matched items: "
        f"{dashboard['supplier_matching_pipeline']['matched_items']}"
    )
    print(
        "RFQ packs: "
        f"{dashboard['rfq_pack_pipeline']['total_rfq_packs']}"
    )
    print(
        "RFQ estimated value: "
        f"R{dashboard['rfq_pack_pipeline']['total_estimated_value']:,.2f}"
    )


if __name__ == "__main__":
    main()
