from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.tender_qualification import qualify_opportunity


RUNTIME_ROOT = PROJECT_ROOT / "runtime" / "manual_production"
REPORT_DIR = RUNTIME_ROOT / "volume_reports"

PHASE1_SAMPLE_DIRS = [
    RUNTIME_ROOT / "e2e_rfqs" / "REAL-PILOT-001-E2E-20260528",
    RUNTIME_ROOT / "e2e_rfqs" / "REAL-PILOT-002",
    RUNTIME_ROOT / "e2e_rfqs" / "REAL-PILOT-002-E2E-20260528",
    RUNTIME_ROOT / "e2e_rfqs" / "REAL-PILOT-003-E2E-20260528",
    RUNTIME_ROOT / "e2e_rfqs" / "RFQ-VALID-001",
    RUNTIME_ROOT / "e2e_rfqs" / "RFQ-VALID-001-E2E-20260528",
    RUNTIME_ROOT / "e2e_rfqs" / "PILOT-005-E2E-20260528",
    RUNTIME_ROOT / "e2e_rfqs" / "HTTPPROBE-20260523190924-E2E-20260528",
    RUNTIME_ROOT / "submission_packages" / "REAL-PILOT-001",
    RUNTIME_ROOT / "e2e_rfqs" / "RFQ-VALID-001",
]

PHASE2_BLOCKED_CASES: List[Tuple[str, Dict[str, Any]]] = [
    (
        "medical_consumables",
        {
            "title": "Medical consumables supply",
            "description": "Medical consumables and clinical supplies delivery by email.",
            "category": "medical consumables",
            "submission_method": "email",
            "buyer_name": "City of Example",
            "province": "Gauteng",
            "estimated_contract_value": 300000.0,
            "reference_number": "MED-001",
        },
    ),
    (
        "it_equipment",
        {
            "title": "IT equipment supply",
            "description": "Laptops, printers, and network equipment delivery by portal.",
            "category": "it equipment",
            "submission_method": "portal",
            "buyer_name": "City of Example",
            "province": "Gauteng",
            "estimated_contract_value": 300000.0,
            "reference_number": "IT-001",
        },
    ),
    (
        "catering",
        {
            "title": "Catering services for event",
            "description": "Catering and refreshments for staff event.",
            "category": "catering",
            "submission_method": "email",
            "buyer_name": "City of Example",
            "province": "Gauteng",
            "estimated_contract_value": 300000.0,
            "reference_number": "CAT-001",
        },
    ),
    (
        "fuel",
        {
            "title": "Fuel supply",
            "description": "Bulk diesel and petrol supply.",
            "category": "fuel",
            "submission_method": "email",
            "buyer_name": "City of Example",
            "province": "Gauteng",
            "estimated_contract_value": 300000.0,
            "reference_number": "FUEL-001",
        },
    ),
    (
        "briefing_session",
        {
            "title": "Supply tender with briefing",
            "description": "Compulsory briefing session required before submission.",
            "submission_method": "email",
            "buyer_name": "City of Example",
            "province": "Gauteng",
            "estimated_contract_value": 300000.0,
            "reference": "BRIEF-001",
            "briefing_required": True,
        },
    ),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _artifact_presence(directory: Path) -> Dict[str, Any]:
    quote_pack_pdf = sorted(directory.glob("*__quote_pack.pdf"))
    quote_pack_json = sorted(directory.glob("*__quote_pack.json"))
    pricing_csv = sorted(directory.glob("*__buyer_pricing_schedule.csv"))
    submission_manifest_json = sorted(directory.glob("*__submission_package_manifest.json"))
    submission_manifest_txt = sorted(directory.glob("*_submission_pack_manifest.txt"))
    zip_files = sorted(directory.glob("*.zip"))
    return {
        "quote_pack_present": bool(quote_pack_pdf or quote_pack_json),
        "pricing_schedule_present": bool(pricing_csv),
        "submission_package_present": bool(submission_manifest_json or submission_manifest_txt or zip_files),
        "submission_zip_present": bool(zip_files),
        "quote_pack_pdf": str(quote_pack_pdf[0]) if quote_pack_pdf else "",
        "quote_pack_json": str(quote_pack_json[0]) if quote_pack_json else "",
        "pricing_csv": str(pricing_csv[0]) if pricing_csv else "",
        "submission_manifest": str((submission_manifest_json or submission_manifest_txt or zip_files)[0]) if (submission_manifest_json or submission_manifest_txt or zip_files) else "",
        "submission_zip": str(zip_files[0]) if zip_files else "",
    }


def run_phase1() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    success_count = 0
    blocked_count = 0
    quote_generation_count = 0
    submission_package_count = 0

    for directory in PHASE1_SAMPLE_DIRS:
        artifact = _artifact_presence(directory)
        success = artifact["quote_pack_present"] and artifact["submission_package_present"]
        blocked = not success
        quote_generation_count += int(artifact["quote_pack_present"])
        submission_package_count += int(artifact["submission_package_present"])
        success_count += int(success)
        blocked_count += int(blocked)
        items.append(
            {
                "rfq_id": directory.name,
                "directory": str(directory),
                **artifact,
                "success": success,
                "blocked": blocked,
            }
        )

    total = len(items) or 1
    return {
        "phase": "phase1_volume_test",
        "sample_size": len(items),
        "success_rate": round(success_count / total, 4),
        "blocked_rate": round(blocked_count / total, 4),
        "quote_generation_rate": round(quote_generation_count / total, 4),
        "submission_package_generation_rate": round(submission_package_count / total, 4),
        "success_count": success_count,
        "blocked_count": blocked_count,
        "quote_generation_count": quote_generation_count,
        "submission_package_generation_count": submission_package_count,
        "items": items,
    }


def _is_blocked(result: Any) -> bool:
    if hasattr(result, "to_dict"):
        result = result.to_dict()
    if isinstance(result, dict):
        if result.get("rejected") is True:
            return True
        if result.get("eligible") is False:
            return True
        if str(result.get("recommendation") or "").upper() == "REJECT":
            return True
        if str(result.get("qualification_status") or "").lower() == "rejected":
            return True
        if str(result.get("classification") or "").lower() == "reject":
            return True
        if bool(result.get("briefing_compulsory")) is True:
            return True
    return False


def run_phase2() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    blocked_count = 0

    for name, payload in PHASE2_BLOCKED_CASES:
        result = qualify_opportunity(payload)
        blocked = _is_blocked(result)
        blocked_count += int(blocked)
        if hasattr(result, "to_dict"):
            result = result.to_dict()
        items.append(
            {
                "case": name,
                "blocked": blocked,
                "result": result,
            }
        )

    total = len(items) or 1
    return {
        "phase": "phase2_rule_validation",
        "sample_size": len(items),
        "blocked_rate": round(blocked_count / total, 4),
        "blocked_count": blocked_count,
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LMCP historical RFQ volume and rule validation report")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()

    phase1 = run_phase1()
    phase2 = run_phase2()
    report = {
        "generated_at": _now(),
        "phase1": phase1,
        "phase2": phase2,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "historical_rfq_volume_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        print(f"Phase 1 sample size: {phase1['sample_size']}")
        print(f"Phase 1 success rate: {phase1['success_rate']:.2%}")
        print(f"Phase 1 blocked rate: {phase1['blocked_rate']:.2%}")
        print(f"Phase 1 quote generation rate: {phase1['quote_generation_rate']:.2%}")
        print(f"Phase 1 submission package generation rate: {phase1['submission_package_generation_rate']:.2%}")
        print(f"Phase 2 sample size: {phase2['sample_size']}")
        print(f"Phase 2 blocked rate: {phase2['blocked_rate']:.2%}")
        print(f"Report written to: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
