from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths
from app.services.live_rfq_store import get_live_rfqs, save_live_rfqs


DEMO_RFQS: List[Dict[str, Any]] = [
    {
        "rfq_id": "REAL-PILOT-001",
        "reference_number": "REAL-PILOT-001",
        "buyer_rfq_number": "REAL-PILOT-001",
        "title": "Supply and Delivery of Office Consumables",
        "buyer_name": "Metro Procurement Unit",
        "province": "Gauteng",
        "submission_type": "email",
        "submission_method": "email",
        "source_name": "Live Portal",
        "source_url": "https://example.org/tenders/one",
        "document_urls": ["https://example.org/tenders/one/rfq.pdf"],
        "category": "supply and delivery",
    }
]


def seed_demo_live_rfq_bundle_if_empty() -> Dict[str, Any]:
    live = get_live_rfqs()
    items = live.get("items") if isinstance(live, dict) else []
    save_live_rfqs(deepcopy(DEMO_RFQS))
    runtime_paths = get_runtime_paths()
    tender_id = DEMO_RFQS[0]["rfq_id"]
    review_dir = runtime_paths.manual_production_dir / "review_ready_bundles" / tender_id
    package_dir = runtime_paths.manual_production_dir / "submission_packages" / tender_id
    source_quotes_dir = package_dir / "source_quotes"
    review_dir.mkdir(parents=True, exist_ok=True)
    source_quotes_dir.mkdir(parents=True, exist_ok=True)
    acme_quote = source_quotes_dir / "Acme_Office_Supplies_quote.txt"
    bright_quote = source_quotes_dir / "Bright_Stationers_quote.txt"
    acme_quote.write_text("Acme quote", encoding="utf-8")
    bright_quote.write_text("Bright quote", encoding="utf-8")
    review_bundle = {
        "created_at": "2026-05-22T08:37:48.977175+00:00",
        "tender_id": tender_id,
        "bundle_status": "ready",
        "review_ready": True,
        "submission_ready": True,
        "reviewReady": True,
        "submissionReady": True,
        "operator_actions_count": 0,
        "audit_events_count": 2,
        "operator_actions": [],
        "audit_events": [],
        "source_quote_entries": [str(acme_quote), str(bright_quote)],
        "live_rfq": {
            "reference": tender_id,
            "title": "Supply and Delivery of Office Consumables",
            "buyer": "Metro Procurement Unit",
            "province": "Gauteng",
            "submissionType": "email",
            "sourceUrl": "https://example.org/tenders/one",
            "documentUrls": ["https://example.org/tenders/one/rfq.pdf"],
        },
        "supplier_quote_comparison": {
            "comparison_status": "ready",
            "supplier_quotes": [
                {"supplier_name": "Acme Office Supplies", "quote_reference": "ACME-001", "quoted_total": 125000.0, "source_file": str(acme_quote)},
                {"supplier_name": "Bright Stationers", "quote_reference": "BRIGHT-002", "quoted_total": 122250.0, "source_file": str(bright_quote)},
            ],
            "recommended_supplier": {"supplier_name": "Bright Stationers", "quote_reference": "BRIGHT-002", "quoted_total": 122250.0},
            "runner_up_supplier": {"supplier_name": "Acme Office Supplies", "quote_reference": "ACME-001", "quoted_total": 125000.0},
            "estimated_savings_vs_runner_up": 2750.0,
            "buyer_item_count": 12,
        },
    }
    (review_dir / "review_ready_quote_pack.json").write_text(json.dumps(review_bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    (review_dir / "review_ready_quote_pack_manifest.json").write_text(
        json.dumps(
            {
                "created_at": review_bundle["created_at"],
                "tender_id": tender_id,
                "bundle_status": "ready",
                "review_ready": True,
                "submission_ready": True,
                "files": [str(acme_quote), str(bright_quote)],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (review_dir / "audit_export.json").write_text("[]", encoding="utf-8")
    (review_dir / "operator_actions.json").write_text("[]", encoding="utf-8")
    (review_dir / "traceability_bundle.json").write_text(
        json.dumps({"live_rfq": review_bundle["live_rfq"], "supplier_quote_comparison": review_bundle["supplier_quote_comparison"]}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    refreshed = get_live_rfqs()
    return {
        "status": "seeded",
        "live_count": len(refreshed.get("items") if isinstance(refreshed, dict) else DEMO_RFQS),
        "existing_live_count": len(items),
        "seed_path": str(get_runtime_paths().runtime_root / "live_rfqs.json"),
    }
