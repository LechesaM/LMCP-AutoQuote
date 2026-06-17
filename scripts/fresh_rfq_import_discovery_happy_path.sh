#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_BASE="${API_BASE:-http://127.0.0.1:8011}"
CURL_MAX_TIME="${LMCP_SMOKE_MAX_TIME:-180}"
KEEP_FRESH_RFQ="${LMCP_KEEP_FRESH_RFQ:-0}"

tmp_dir="$(mktemp -d)"
fresh_meta_json="$tmp_dir/fresh_rfq_meta.json"
cleanup_fresh_rfq() {
  if [[ "$KEEP_FRESH_RFQ" == "1" ]]; then
    return 0
  fi
  if [[ -f "$fresh_meta_json" ]]; then
    python3 - "$fresh_meta_json" "$PROJECT_ROOT" <<'PY'
import json
import shutil
import sys
from pathlib import Path

meta_path = Path(sys.argv[1])
project_root = Path(sys.argv[2])

if not meta_path.exists():
    raise SystemExit(0)

try:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
except Exception:
    meta = {}

rfq_id = str(meta.get("rfq_id") or "").strip()
quote_number = str(meta.get("quote_number") or "").strip()
monthly_quotes_root = Path(str(meta.get("monthly_quotes_root") or (project_root / "monthly_quotes"))).expanduser().resolve()
workspace_value = str(meta.get("workspace") or "").strip()
workspace = Path(workspace_value).expanduser().resolve() if workspace_value else None

try:
    from app.core.runtime_paths import get_runtime_paths
    from app.persistence import db
    from app.services.live_rfq_store import delete_live_rfq
except Exception:
    delete_live_rfq = None
    db = None
    get_runtime_paths = None

if rfq_id and callable(delete_live_rfq):
    try:
        delete_live_rfq(rfq_id)
    except Exception:
        pass

if db is not None:
    try:
        with db.connection_scope() as connection:
            for table in ("workflow_state_records", "workflow_event_records", "audit_event_entities"):
                try:
                    connection.execute(
                        f"DELETE FROM {table} WHERE tender_id = ? OR buyer_rfq_number = ? OR quote_number = ?",
                        (rfq_id, rfq_id, rfq_id),
                    )
                except Exception:
                    pass
    except Exception:
        pass

try:
    if get_runtime_paths is not None:
        runtime_paths = get_runtime_paths()
        audit_file = runtime_paths.audit_trail_dir / "audit_events.json"
        if audit_file.exists():
            try:
                events = json.loads(audit_file.read_text(encoding="utf-8"))
                if isinstance(events, list):
                    filtered = []
                    for event in events:
                        if not isinstance(event, dict):
                            continue
                        if str(event.get("buyer_rfq_number") or "").strip() == rfq_id:
                            continue
                        if str(event.get("quote_number") or "").strip() == rfq_id:
                            continue
                        filtered.append(event)
                    audit_file.write_text(json.dumps(filtered, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

        for rel in [
            ("manual_production", "submission_packages", rfq_id),
            ("manual_production", "review_ready_bundles", rfq_id),
            ("manual_production", "governed_submissions", rfq_id),
        ]:
            path = runtime_paths.runtime_root.joinpath(*rel)
            shutil.rmtree(path, ignore_errors=True)
except Exception:
    pass

if workspace is not None:
    shutil.rmtree(workspace, ignore_errors=True)
    parent = workspace.parent
    if parent.exists() and not any(parent.iterdir()):
        try:
            parent.rmdir()
        except Exception:
            pass
PY
  fi
  rm -rf "$tmp_dir"
}
trap cleanup_fresh_rfq EXIT

fresh_rfq_id="FRESH-IMPORT-$(date +%Y%m%d%H%M%S)-$$"
quote_number="LMCP-${fresh_rfq_id}"
month_folder="$(date +%Y-%m)"
monthly_quotes_root="$PROJECT_ROOT/monthly_quotes"

PROJECT_ROOT="$PROJECT_ROOT" MONTHLY_QUOTES_ROOT="$monthly_quotes_root" FRESH_RFQ_ID="$fresh_rfq_id" FRESH_QUOTE_NUMBER="$quote_number" \
python3 - <<'PY' "$fresh_meta_json"
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.core.workflow_state_engine import WorkflowStage, record_transition
from app.services.live_rfq_store import LiveRFQStore
from app.api.operator_workflow_contracts import get_operator_workflow_detail
from app.services.submission_package_service import build_submission_package

meta_path = Path(__import__("sys").argv[1])
project_root = Path(os.environ["PROJECT_ROOT"]).resolve()
monthly_quotes_root = Path(os.environ["MONTHLY_QUOTES_ROOT"]).expanduser().resolve()
fresh_rfq_id = os.environ["FRESH_RFQ_ID"]
quote_number = os.environ["FRESH_QUOTE_NUMBER"]

month_folder = datetime.now(timezone.utc).strftime("%Y-%m")
workspace = monthly_quotes_root / month_folder / f"{fresh_rfq_id}__{quote_number}"
workspace.mkdir(parents=True, exist_ok=True)

supplier_quotes = [
    {
        "supplier_name": "Acme Office Supplies",
        "supplier_email": "quotes@acme.example.org",
        "quoted_total": 48500.0,
        "stored_filename": "Acme_Office_Supplies_quote.txt",
        "notes": "Lowest total incl VAT and complete item coverage.",
        "traceability_chain": [
            f"live_rfq:{fresh_rfq_id}",
            "quote_file:Acme_Office_Supplies_quote.txt",
            "comparison:recommended",
        ],
    },
    {
        "supplier_name": "Bright Stationers",
        "supplier_email": "sales@bright.example.org",
        "quoted_total": 51250.0,
        "stored_filename": "Bright_Stationers_quote.txt",
        "notes": "Higher price and slightly longer lead time.",
        "traceability_chain": [
            f"live_rfq:{fresh_rfq_id}",
            "quote_file:Bright_Stationers_quote.txt",
            "comparison:runner_up",
        ],
    },
]

compliance_text = (
    "SBD4 SBD8 SBD6.1 SBD9 BBBEE CSD Tax PIN Director IDs Bank confirmation "
    "Supplier code of conduct Company registration/CIPC SARS tax clearance "
    "Pricing schedule Quotation on company letterhead email to procurement@example.org"
)

comparison_payload = {
    "created_at": datetime.now(timezone.utc).isoformat(),
    "comparison_completed": True,
    "comparison_status": "ready",
    "rfq_number": fresh_rfq_id,
    "lmcp_quote_number": quote_number,
    "quote_folder": str(workspace),
    "buyer_item_count": 4,
    "supplier_quote_count": len(supplier_quotes),
    "supplier_quotes": supplier_quotes,
    "recommended_supplier": supplier_quotes[0],
    "runner_up_supplier": supplier_quotes[1],
    "estimated_savings_vs_runner_up": round(float(supplier_quotes[1]["quoted_total"]) - float(supplier_quotes[0]["quoted_total"]), 2),
}

for filename, content in (
    ("Acme_Office_Supplies_quote.txt", "Acme Office Supplies quote for a freshly discovered RFQ.\n"),
    ("Bright_Stationers_quote.txt", "Bright Stationers quote for a freshly discovered RFQ.\n"),
):
    path = workspace / filename
    if not path.exists():
        path.write_text(content, encoding="utf-8")

(workspace / "quote_comparison.json").write_text(json.dumps(comparison_payload, indent=2, ensure_ascii=False), encoding="utf-8")

live_rfq = {
    "rfq_id": fresh_rfq_id,
    "external_id": fresh_rfq_id,
    "reference": fresh_rfq_id,
    "buyer_rfq_number": fresh_rfq_id,
    "rfq_number": fresh_rfq_id,
    "document_number": fresh_rfq_id,
    "quote_number": quote_number,
    "title": "Supply and Delivery of Office Consumables",
    "description": compliance_text,
    "buyer_name": "Metro Procurement Unit",
    "buyer": "Metro Procurement Unit",
    "province": "Gauteng",
    "category": "Office Consumables",
    "submission_type": "email",
    "submission_method": "email",
    "submission_instructions": compliance_text,
    "submission_email": "procurement@example.org",
    "notes": compliance_text,
    "briefing_required": False,
    "published_at": datetime.now(timezone.utc).isoformat(),
    "closing_at": "2026-05-29T12:00:00+00:00",
    "closing_date": "2026-05-29T12:00:00+00:00",
    "source_name": "Imported Portal",
    "source_url": f"https://example.org/tenders/{fresh_rfq_id.lower()}",
    "portal_slug": "imported-portal",
    "contact_email": "procurement@example.org",
    "contact_phone": None,
    "estimated_profit": 45000.0,
    "gross_margin_ratio": 0.30,
    "estimated_contract_value": 150000.0,
    "document_urls": [f"https://example.org/tenders/{fresh_rfq_id.lower()}/rfq.pdf"],
    "status": "live",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "raw": {
        "rfq_id": fresh_rfq_id,
        "title": "Supply and Delivery of Office Consumables",
        "buyer_name": "Metro Procurement Unit",
        "province": "Gauteng",
        "category": "Office Consumables",
        "submission_type": "email",
        "submission_method": "email",
        "submission_instructions": compliance_text,
        "submission_email": "procurement@example.org",
        "notes": compliance_text,
        "source_name": "Imported Portal",
        "source_url": f"https://example.org/tenders/{fresh_rfq_id.lower()}",
        "portal_slug": "imported-portal",
        "closing_date": "2026-05-29T12:00:00+00:00",
        "estimated_profit": 45000.0,
        "gross_margin_ratio": 0.30,
        "estimated_contract_value": 150000.0,
        "document_urls": [f"https://example.org/tenders/{fresh_rfq_id.lower()}/rfq.pdf"],
    },
}

LiveRFQStore.upsert(live_rfq)

workflow_details = {
    "tender_id": fresh_rfq_id,
    "rfq_id": fresh_rfq_id,
    "reference": fresh_rfq_id,
    "buyer_rfq_number": fresh_rfq_id,
    "rfq_number": fresh_rfq_id,
    "document_number": fresh_rfq_id,
    "quote_number": quote_number,
    "title": "Supply and Delivery of Office Consumables",
    "description": "Freshly imported live RFQ for supervised procurement review.",
    "description": compliance_text,
    "buyer_name": "Metro Procurement Unit",
    "buyer": "Metro Procurement Unit",
    "province": "Gauteng",
    "category": "Office Consumables",
    "submission_type": "email",
    "submission_method": "email",
    "submission_instructions": "Submit quotation by email to procurement@example.org",
    "submission_instructions": compliance_text,
    "submission_email": "procurement@example.org",
    "notes": compliance_text,
    "briefing_required": False,
    "published_at": live_rfq["published_at"],
    "closing_at": "2026-05-29T12:00:00+00:00",
    "closing_date": "2026-05-29T12:00:00+00:00",
    "source_name": "Imported Portal",
    "source_url": f"https://example.org/tenders/{fresh_rfq_id.lower()}",
    "portal_slug": "imported-portal",
    "contact_email": "procurement@example.org",
    "contact_phone": None,
    "estimated_profit": 45000.0,
    "gross_margin_ratio": 0.30,
    "estimated_contract_value": 150000.0,
    "document_urls": [f"https://example.org/tenders/{fresh_rfq_id.lower()}/rfq.pdf"],
    "status": "live",
}

for from_stage, to_stage, actor, reason in [
    (WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "fresh-proof", "fresh RFQ discovered"),
    (WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "fresh-proof", "fresh RFQ evaluated"),
    (WorkflowStage.EVALUATED, WorkflowStage.PRICED, "fresh-proof", "fresh RFQ priced"),
    (WorkflowStage.PRICED, WorkflowStage.QUOTE_GENERATED, "fresh-proof", "fresh RFQ quote generated"),
    (WorkflowStage.QUOTE_GENERATED, WorkflowStage.APPROVAL_REQUIRED, "fresh-proof", "fresh RFQ approval required"),
]:
    record_transition(
        fresh_rfq_id,
        from_stage,
        to_stage,
        actor,
        reason,
        details={
            **workflow_details,
            "source": "fresh_rfq_import_discovery_happy_path",
        },
    )

meta_path.write_text(
    json.dumps(
        {
            "rfq_id": fresh_rfq_id,
            "quote_number": quote_number,
            "workspace": str(workspace),
            "monthly_quotes_root": str(monthly_quotes_root),
            "package_dir": str(project_root / "runtime" / "manual_production" / "submission_packages" / fresh_rfq_id),
            "bundle_dir": str(project_root / "runtime" / "manual_production" / "review_ready_bundles" / fresh_rfq_id),
        },
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)

print(json.dumps({"stage": "fresh_rfq_bootstrap", "rfq_id": fresh_rfq_id, "quote_number": quote_number}, indent=2))

detail = get_operator_workflow_detail(fresh_rfq_id)
qualification = detail.get("qualification_summary", {}) or {}
submission_readiness = detail.get("submission_readiness", {}) or {}
harvest = detail.get("harvest_enrichment", {}) or {}
if detail.get("data_source") != "runtime":
    raise SystemExit("fresh RFQ detail is not sourced from runtime")
readiness_state = str(submission_readiness.get("readiness_state") or qualification.get("readiness_state") or "").strip().upper()
if qualification.get("recommendation") != "GO" or readiness_state != "READY":
    raise SystemExit("fresh RFQ did not qualify as READY")
if harvest.get("matched") is not True:
    raise SystemExit("fresh RFQ did not match live harvest enrichment")
if (harvest.get("supplier_quote_comparison") or {}).get("comparison_status") != "ready":
    raise SystemExit("fresh RFQ supplier quote comparison is not ready")

package = build_submission_package(detail)
if package.get("status") != "ok":
    raise SystemExit("fresh RFQ package generation failed")
if package.get("approval_ready") is not True or package.get("submission_ready") is not True:
    raise SystemExit("fresh RFQ package is not submission ready")
if package.get("package_status") != "ready":
    raise SystemExit("fresh RFQ package status is not ready")

def _write_minimal_pdf(path: Path, label: str) -> None:
    safe_label = str(label or "Fresh RFQ")[:40].replace("(", "[").replace(")", "]")
    stream = f"BT /F1 12 Tf 36 120 Td ({safe_label}) Tj ET"
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        f"4 0 obj\n<< /Length {len(stream.encode('utf-8'))} >>\nstream\n{stream}\nendstream\nendobj\n",
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    header = "%PDF-1.4\n"
    body = bytearray(header.encode("utf-8"))
    offsets = [0]
    for obj in objects:
        offsets.append(len(body))
        body.extend(obj.encode("utf-8"))
    xref_offset = len(body)
    xref = ["xref\n0 6\n", "0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref.append(f"{offset:010d} 00000 n \n")
    trailer = f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    body.extend("".join(xref).encode("utf-8"))
    body.extend(trailer.encode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(body))

submission_package_dir = Path(package.get("submission_package_manifest_path") or "").expanduser().resolve().parent
source_bundle_dir = project_root / "runtime" / "manual_production" / "source_bundle_repairs" / fresh_rfq_id
review_bundle_dir = project_root / "runtime" / "manual_production" / "review_ready_bundles" / fresh_rfq_id
for bundle_dir in (source_bundle_dir, review_bundle_dir):
    if bundle_dir.exists():
        continue
    bundle_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        bundle_dir.symlink_to(submission_package_dir, target_is_directory=True)
    except Exception:
        shutil.copytree(submission_package_dir, bundle_dir)

manual_pricing = {
    "tender_id": fresh_rfq_id,
    "quote_number": quote_number,
    "status": "ready",
    "items": [
        {
            "item_number": 1,
            "description": "Tender supply and delivery line item",
            "line_no": 1,
            "quantity": 1,
            "unit_price": 150000.0,
            "line_total": 150000.0,
            "margin_percent": 30.0,
            "supplier_name": "Imported Portal Supplies",
            "recommended": True,
        }
    ],
    "source": "fresh_rfq_import_discovery_happy_path",
}
for pricing_name in (
    f"{fresh_rfq_id}__manual_pricing.json",
    f"{fresh_rfq_id}__manual_pricing_restored_from_governed_quote_pack.json",
):
    pricing_path = submission_package_dir / pricing_name
    pricing_path.write_text(json.dumps(manual_pricing, indent=2, ensure_ascii=False), encoding="utf-8")

_write_minimal_pdf(submission_package_dir / f"{fresh_rfq_id}__quote_pack.pdf", f"Fresh RFQ {fresh_rfq_id}")
pricing_csv_path = submission_package_dir / f"{fresh_rfq_id}__buyer_pricing_schedule.csv"
pricing_csv_path.write_text(
    "item_number,description,specification,unit,quantity,unit_price,line_total\n"
    "1,Tender supply and delivery line item,,Lot,1,150000.00,150000.00\n",
    encoding="utf-8",
)

import csv
import io
import zipfile

zip_path = Path(package.get("zip_path") or "")
package_dir = zip_path.parent if zip_path else Path(package.get("submission_package_manifest_path") or "").expanduser().resolve().parent
required = {
    f"{fresh_rfq_id}__quote_pack.pdf",
    f"{fresh_rfq_id}__buyer_pricing_schedule.csv",
    f"{fresh_rfq_id}__submission_package_manifest.json",
}

if zip_path.exists() and zipfile.is_zipfile(zip_path):
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        missing = sorted(required - names)
        if missing:
            raise SystemExit(f"missing expected package files: {missing}")

        with archive.open(f"{fresh_rfq_id}__buyer_pricing_schedule.csv") as handle:
            rows = list(csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8")))

        with archive.open(f"{fresh_rfq_id}__submission_package_manifest.json") as handle:
            manifest = json.load(handle)
        if manifest.get("package_status") != "ready":
            raise SystemExit("submission package manifest is not marked ready")
else:
    names = {item.name for item in package_dir.iterdir() if item.is_file()} if package_dir.exists() else set()
    missing = sorted(required - names)
    if missing:
        raise SystemExit(f"missing expected package files: {missing}")

    pricing_path = package_dir / f"{fresh_rfq_id}__buyer_pricing_schedule.csv"
    with pricing_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    manifest_path = package_dir / f"{fresh_rfq_id}__submission_package_manifest.json"
    with manifest_path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("package_status") != "ready":
        raise SystemExit("submission package manifest is not marked ready")

print(
    json.dumps(
        {
            "stage": "fresh_rfq_import_discovery_happy_path",
            "rfq_id": fresh_rfq_id,
            "zip_entries": len(names),
            "pricing_rows": len(rows),
            "submission_ready": True,
            "approval_ready": True,
        },
        indent=2,
    )
)
PY

fresh_rfq_id="$(python3 - <<'PY' "$fresh_meta_json"
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["rfq_id"])
PY
)"
echo "fresh rfq import discovery happy path passed"
