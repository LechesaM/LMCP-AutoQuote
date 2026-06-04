from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _seed_controlled_runtime(runtime_dir: Path) -> None:
    policy = {
        "enabled": True,
        "mode": "controlled",
        "allow_email_send": False,
        "allow_portal_upload": False,
        "allow_portal_final_submit": False,
        "require_confirmation_phrase": True,
        "confirmation_phrase": "I CONFIRM FINAL SUBMISSION",
        "minimum_profit_required": 30000.0,
        "margin_percent": 25.0,
        "apply_profit_floor": True,
        "min_confidence": 0.35,
        "zip_allowed_for_submission": False,
        "captcha_bypass_allowed": False,
    }
    state = {
        "system_on": True,
        "harvest_paused": False,
        "submission_paused": False,
        "emergency_stop": False,
        "updated_at": _now_iso(),
        "reason": "controlled runtime proof",
        "last_changed_by": "system",
        "control_mode": "controlled",
        "effective_system_status": "controlled",
        "policy": policy,
    }

    _write_json(runtime_dir / "system_control" / "v48_autonomous_state.json", state)
    _write_json(runtime_dir / "full_autonomous_v48" / "policy.json", policy)

    live_rfq = {
        "status": "ok",
        "updated_at": _now_iso(),
        "count": 1,
        "items": [
            {
                "id": "CTRL-001",
                "rfq_reference": "CTRL-001",
                "buyer_rfq_number": "CTRL-001",
                "reference_number": "LMCP-CTRL-001",
                "title": "Controlled validation supply bundle",
                "buyer": "Controlled Buyer (Pty) Ltd",
                "buyer_name": "Controlled Buyer (Pty) Ltd",
                "estimated_value": 184000,
                "estimated_profit": 40000,
                "margin_percent": 25,
                "recommended_next_step": "Generate local quote pack for operator review",
                "readiness": {
                    "pricing_schedule_found": True,
                    "boq_found": True,
                    "buyer_forms_found": True,
                    "sbd_forms_found": True,
                    "missing_items": [],
                },
                "artifacts": {
                    "pricing_schedules": [],
                    "boqs": [],
                    "buyer_docs": [],
                    "sbd_forms": [],
                },
                "manual_pricing_verified": True,
                "manual_pricing": {
                    "line_items": [
                        {
                            "line_no": 1,
                            "description": "Controlled validation supply bundle",
                            "unit": "Each",
                            "quantity": 1,
                            "unit_cost": 120000,
                            "markup_percent": 33.3333,
                            "pricing_status": "priced",
                        }
                    ],
                    "totals": {
                        "subtotal_ex_vat": 160000,
                        "vat_amount": 24000,
                        "total_incl_vat": 184000,
                    },
                    "validation": {"status": "ok"},
                    "saved_at": _now_iso(),
                },
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            }
        ],
    }
    _write_json(runtime_dir / "rfq_lifecycle" / "rfqs.json", live_rfq)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the controlled LMCP runtime proof locally.")
    parser.add_argument("--runtime-dir", default=os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime"))
    parser.add_argument("--pack-id", default="CTRL-001__LMCP-CTRL-001")
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Seed the controlled runtime state and exit without running the proof chain.",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip runtime seeding and run only the proof chain against the existing runtime state.",
    )
    args = parser.parse_args()

    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    runtime_dir.mkdir(parents=True, exist_ok=True)
    os.environ["LMCP_RUNTIME_DIR"] = str(runtime_dir)

    # Keep the proof self-contained and local.
    os.environ.setdefault("DATABASE_URL", "sqlite:////private/tmp/lmcp_autoquote.db")

    if not args.skip_seed:
        _seed_controlled_runtime(runtime_dir)

    if args.seed_only:
        print(
            json.dumps(
                {
                    "runtime_dir": str(runtime_dir),
                    "seeded": True,
                    "controlled_policy": {
                        "mode": "controlled",
                        "allow_email_send": False,
                        "allow_portal_upload": False,
                        "allow_portal_final_submit": False,
                    },
                },
                indent=2,
            )
        )
        return 0

    from app.services.amount_quantity_integrity_validation_engine import validate_amount_quantity_integrity
    from app.services.quote_compilation_service import QuoteCompilationService
    from app.services.quote_pack_service import QuotePackService
    from app.services.quote_review_service import validate_quote_pack
    from app.services.submission_pack_assembler_service import build_submission_pack
    from app.quote_pack_models import QuotePack, QuotePackItem

    pack_id = args.pack_id
    quote_folder = runtime_dir / "generated_quotes" / pack_id

    preflight = validate_amount_quantity_integrity(
        [
            {
                "description": "Controlled validation supply bundle",
                "quantity": 1,
                "unit": "Each",
                "unit_price": 160000,
            }
        ],
        attach_debug=True,
    )

    quote_payload = {
        "buyer_name": "Controlled Buyer (Pty) Ltd",
        "buyer_rfq_number": "CTRL-001",
        "rfq_number": "CTRL-001",
        "quote_number": "LMCP-CTRL-001",
        "title": "Controlled validation supply bundle",
        "quote_folder": str(quote_folder),
        "items": [
            {
                "line_number": 1,
                "description": "Controlled validation supply bundle",
                "unit": "Each",
                "quantity": 1,
                "unit_price": 160000,
                "line_total": 160000,
                "vat_amount": 24000,
                "amount_incl_vat": 184000,
            }
        ],
        "estimated_revenue": 184000,
        "estimated_cost": 120000,
        "estimated_profit": 40000,
        "estimated_margin": 0.25,
    }

    quote_pack = QuotePackService.generate_quote_pack(quote_payload)
    quote_pack_pdf = Path(quote_pack["pdf_path"])

    validation_quote = QuotePack(
        quote_number="LMCP-CTRL-001",
        client_name="Controlled Buyer (Pty) Ltd",
        project_title="Controlled validation supply bundle",
        rfq_reference="CTRL-001",
        subtotal=160000,
        vat_rate=0.15,
        vat_amount=24000,
        total_amount=184000,
        estimated_profit=40000,
        estimated_margin_percent=25.0,
        briefing_required=False,
        approval_required=True,
        classification_payload_json=json.dumps({"decision": "included", "reasons": []}),
        compliance_payload_json=json.dumps([]),
        pricing_payload_json=json.dumps({"items": quote_payload["items"]}),
    )
    validation_quote.items = [
        QuotePackItem(
            quote_pack_id=1,
            item_no=1,
            description="Controlled validation supply bundle",
            unit="Each",
            quantity=1,
            unit_price=160000,
            line_total=160000,
            supplier_cost=120000,
            delivery_cost=0,
            margin_percent=25.0,
            final_quoted_price=160000,
            buyer_row_code="CTRL-001-1",
            buyer_row_text="Controlled validation supply bundle",
            mapping_confidence=1.0,
            requires_manual_review=False,
        )
    ]
    quote_validation = validate_quote_pack(validation_quote)

    compiler = QuoteCompilationService()
    pricing = compiler.save_local_pricing(
        pack_id,
        {
            "items": [
                {
                    "line_no": 1,
                    "description": "Controlled validation supply bundle",
                    "unit": "Each",
                    "quantity": 1,
                    "unit_cost": 120000,
                    "markup_percent": 33.3333,
                    "pricing_status": "priced",
                }
            ],
            "vat_rate": 15.0,
            "currency": "ZAR",
        },
    )

    submission_pack = build_submission_pack(
        {
            "rfq_number": "CTRL-001",
            "reference_number": "LMCP-CTRL-001",
            "buyer_name": "Controlled Buyer (Pty) Ltd",
            "title": "Controlled validation supply bundle",
            "quote_pack_pdf_path": str(quote_pack_pdf),
            "rendered_buyer_pdf_path": str(quote_pack_pdf),
            "metadata": {
                "pdf_output_dir": str(runtime_dir / "generated_quotes"),
                "buyer_name": "Controlled Buyer (Pty) Ltd",
                "title": "Controlled validation supply bundle",
                "buyer_rfq_number": "CTRL-001",
                "compliance_document_paths": [],
                "extra_submission_paths": [],
            },
            "review_rows": [],
            "line_items": quote_pack.get("line_items") or quote_pack.get("items") or [],
        }
    )

    result = {
        "runtime_dir": str(runtime_dir),
        "controlled_policy": {
            "mode": "controlled",
            "allow_email_send": False,
            "allow_portal_upload": False,
            "allow_portal_final_submit": False,
        },
        "preflight_validation": preflight,
        "quote_pack": {
            "pack_id": pack_id,
            "pdf_path": str(quote_pack_pdf),
            "quote_number": quote_pack.get("quote_number"),
            "buyer_rfq_number": quote_pack.get("buyer_rfq_number"),
            "estimated_profit": quote_pack.get("estimated_profit"),
            "estimated_margin": quote_pack.get("estimated_margin"),
        },
        "quote_validation": quote_validation,
        "pricing_schedule": pricing,
        "submission_pack": submission_pack,
        "safety": {
            "no_portal_upload": True,
            "no_email_send": True,
            "no_final_submit": True,
        },
    }

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
