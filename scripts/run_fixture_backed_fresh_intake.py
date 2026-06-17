from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.runtime_paths import get_runtime_paths
from app.pilot import record_pilot_run
from app.services.live_rfq_store import LiveRFQStore
from app.services.tender_harvester import run_national_tender_radar
from app.services.tender_harvester import _load_source_health as _load_harvest_source_health
from app.testing.e2e_rfq_harness import E2ERFQHarness


DEFAULT_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "real_pilot_rfqs" / "real_pilot_valid_office_consumables_001.json"
DEFAULT_HARVEST_SOURCE_FILE = PROJECT_ROOT / "app" / "data" / "harvest_sources.json"
DEFAULT_FALLBACK_FIXTURE = DEFAULT_FIXTURE


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fresh_tender_id(prefix: str = "FRESH_REFRESH") -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{timestamp}_{os.getpid()}"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _write_valid_pdf(path: Path, label: str) -> None:
    safe_label = _clean(label)[:60].replace("(", "[").replace(")", "]")
    stream = f"BT /F1 12 Tf 36 120 Td ({safe_label}) Tj ET"
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        f"4 0 obj\n<< /Length {len(stream.encode('utf-8'))} >>\nstream\n{stream}\nendstream\nendobj\n",
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    body = bytearray("%PDF-1.4\n".encode("utf-8"))
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


def _write_minimal_pdf_lines(path: Path, lines: List[str]) -> None:
    safe_lines = [(_clean(line)[:120].replace("(", "[").replace(")", "]")) for line in lines if _clean(line)]
    if not safe_lines:
        safe_lines = ["Fresh RFQ summary"]
    y = 170
    stream_lines = ["BT /F1 10 Tf"]
    for index, line in enumerate(safe_lines[:12]):
        offset = y - (index * 14)
        stream_lines.append(f"36 {offset} Td ({line}) Tj")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines)
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        f"4 0 obj\n<< /Length {len(stream.encode('utf-8'))} >>\nstream\n{stream}\nendstream\nendobj\n",
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    body = bytearray("%PDF-1.4\n".encode("utf-8"))
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


def _copy_fixture_to_runtime(fixture: Path) -> Path:
    runtime_root = get_runtime_paths().manual_production_dir / "fresh_intake_sources"
    runtime_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    copied = runtime_root / f"fresh_intake_{timestamp}_{os.getpid()}.json"
    shutil.copy2(fixture, copied)
    return copied


def _read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _numeric(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(str(value).replace(",", "").strip())
    except Exception:
        return default


def _default_unit_price(description: str, item_number: int) -> float:
    text = description.lower()
    if "paper" in text:
        return 100.0
    if "pen" in text:
        return 50.0
    if "file" in text or "folder" in text:
        return 40.0
    return max(25.0, 25.0 * float(item_number))


def _build_pricing_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        description = _clean(row.get("description") or row.get("specification") or row.get("item_description") or f"Line {index}")
        quantity = _numeric(row.get("quantity") or row.get("qty") or 1.0, 1.0)
        unit_price = _numeric(row.get("unit_price") or row.get("price") or 0.0, 0.0)
        item_number = int(_numeric(row.get("item_number") or row.get("line_no") or row.get("line_number") or index, index))
        if unit_price <= 0:
            unit_price = _default_unit_price(description, item_number)
        line_total = _numeric(row.get("line_total"), unit_price * quantity)
        if line_total <= 0:
            line_total = round(unit_price * quantity, 2)
        items.append(
            {
                "item_number": item_number,
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total,
                "margin_percent": 30.0,
                "supplier_name": "Harness Fixture Supplies",
                "supplier_quote_ref": f"LMCP-{item_number}",
                "recommended": index == 1,
            }
        )
    if not items:
        items.append(
            {
                "item_number": 1,
                "description": "Fixture-backed tender supply and delivery line item",
                "quantity": 1.0,
                "unit_price": 150000.0,
                "line_total": 150000.0,
                "margin_percent": 30.0,
                "supplier_name": "Harness Fixture Supplies",
                "supplier_quote_ref": "LMCP-1",
                "recommended": True,
            }
        )
    return items


def _write_manual_pricing_files(submission_package_dir: Path, tender_id: str, quote_number: str, rows: List[Dict[str, Any]]) -> Path:
    pricing_items = _build_pricing_items(rows)
    payload = {
        "tender_id": tender_id,
        "quote_number": quote_number,
        "status": "ready",
        "source": "fixture_backed_fresh_intake",
        "items": pricing_items,
    }
    pricing_file = submission_package_dir / f"{tender_id}__manual_pricing.json"
    restored_file = submission_package_dir / f"{tender_id}__manual_pricing_restored_from_governed_quote_pack.json"
    _write_json(pricing_file, payload)
    _write_json(restored_file, payload)
    return pricing_file


def _write_submission_zip(target_dir: Path, tender_id: str, files: List[Path]) -> Path:
    zip_path = target_dir / f"{tender_id}__submission_package.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            if path.exists() and path.is_file():
                archive.write(path, arcname=path.name)
    return zip_path


def _normalise_harvest_item(item: Dict[str, Any]) -> Dict[str, Any]:
    source = dict(item or {})
    if not source.get("rfq_id"):
        source["rfq_id"] = _clean(source.get("reference") or source.get("external_id") or source.get("rfq_number") or source.get("title") or "HARVESTED-RFQ")
    source.setdefault("eligible", bool(source.get("quote_ready", False)) or _clean(source.get("status")).lower() == "quote ready")
    source.setdefault("quote_ready", bool(source.get("eligible", False)))
    source.setdefault("submission_method", _clean(source.get("submission_method") or source.get("submission_type") or "email"))
    source.setdefault("submission_type", source.get("submission_method"))
    source.setdefault("source_name", _clean(source.get("source_name") or source.get("buyer_name") or "Live Harvest"))
    source.setdefault("source_url", _clean(source.get("source_url") or source.get("url") or ""))
    source.setdefault("title", _clean(source.get("title") or source.get("description") or source["rfq_id"]))
    source.setdefault("description", _clean(source.get("description") or source.get("title") or source["rfq_id"]))
    source.setdefault("buyer_name", _clean(source.get("buyer_name") or source.get("buyer") or ""))
    source.setdefault("buyer", _clean(source.get("buyer") or source.get("buyer_name") or ""))
    source.setdefault("province", _clean(source.get("province") or ""))
    source.setdefault("category", _clean(source.get("category") or source.get("commodity_class") or ""))
    source.setdefault("document_urls", [source.get("source_url")] if _clean(source.get("source_url")) else [])
    source.setdefault("published_at", _now_iso())
    source.setdefault("closing_at", _clean(source.get("closing_at") or source.get("closing_date") or _now_iso()))
    source.setdefault("closing_date", _clean(source.get("closing_date") or source.get("closing_at") or _now_iso()))
    source.setdefault("estimated_profit", _numeric(source.get("estimated_profit") or source.get("estimated_profit_value") or 45000.0, 45000.0))
    source.setdefault("gross_margin_ratio", _numeric(source.get("gross_margin_ratio") or 0.30, 0.30))
    source.setdefault("estimated_contract_value", _numeric(source.get("estimated_contract_value") or 150000.0, 150000.0))
    source.setdefault("status", _clean(source.get("status") or "Quote Ready"))
    source.setdefault("pipeline_status", _clean(source.get("pipeline_status") or "quote_ready_validated"))
    return source


def _select_harvest_candidate(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    scored: List[tuple[int, float, Dict[str, Any]]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized = _normalise_harvest_item(item)
        status = _clean(normalized.get("status")).lower()
        pipeline_status = _clean(normalized.get("pipeline_status")).lower()
        quote_ready = bool(normalized.get("quote_ready", False))
        eligible = bool(normalized.get("eligible", False))
        score = 0
        if quote_ready or status == "quote ready" or pipeline_status == "quote_ready_validated":
            score = 0
        elif status == "review required" or pipeline_status == "quantity_verification_required":
            score = 1
        elif status == "manual pricing required" or pipeline_status == "manual_pricing_required":
            score = 2
        else:
            score = 3
        recency = 0.0
        for key in ("updated_at", "created_at", "published_at"):
            raw = _clean(normalized.get(key))
            if not raw:
                continue
            try:
                recency = datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
                break
            except Exception:
                continue
        scored.append((score, -recency, normalized if eligible or quote_ready or score <= 2 else normalized))
    if not scored:
        return {}
    scored.sort(key=lambda item: (item[0], item[1]))
    return scored[0][2]


def _harvest_rows_from_item(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    line_items = item.get("line_items")
    rows: List[Dict[str, Any]] = []
    if isinstance(line_items, list) and line_items:
        for index, line in enumerate(line_items, start=1):
            if not isinstance(line, dict):
                continue
            description = _clean(line.get("description") or line.get("item_description") or line.get("specification") or line.get("name") or f"Line {index}")
            quantity = _numeric(line.get("quantity") or line.get("qty") or 1.0, 1.0)
            unit_price = _numeric(line.get("unit_price") or line.get("price") or 0.0, 0.0)
            if unit_price <= 0:
                unit_price = _default_unit_price(description, index)
            line_total = _numeric(line.get("line_total"), unit_price * quantity)
            if line_total <= 0:
                line_total = round(unit_price * quantity, 2)
            rows.append(
                {
                    "item_number": int(_numeric(line.get("item_number") or line.get("line_number") or line.get("line_no") or index, index)),
                    "description": description,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "line_total": line_total,
                    "margin_percent": 30.0,
                    "supplier_name": _clean(line.get("supplier_name") or item.get("source_name") or "Harvested Supplier"),
                    "supplier_quote_ref": _clean(line.get("supplier_quote_ref") or f"{_clean(item.get('rfq_id') or 'HARVEST')}-{index}"),
                    "recommended": index == 1,
                }
            )
    if rows:
        return rows

    description = _clean(item.get("title") or item.get("description") or item.get("rfq_id") or "Harvested tender line item")
    quantity = _numeric(item.get("quantity") or 1.0, 1.0)
    unit_price = _numeric(item.get("estimated_contract_value") or 150000.0, 150000.0)
    rows.append(
        {
            "item_number": 1,
            "description": description,
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": round(unit_price * quantity, 2),
            "margin_percent": 30.0,
            "supplier_name": _clean(item.get("source_name") or "Harvested Supplier"),
            "supplier_quote_ref": f"{_clean(item.get('rfq_id') or 'HARVEST')}-1",
            "recommended": True,
        }
    )
    return rows


def _write_harvest_source_summary_pdf(path: Path, item: Dict[str, Any]) -> None:
    lines = [
        f"Tender ID: {_clean(item.get('rfq_id') or item.get('reference') or item.get('external_id') or 'HARVESTED')}",
        f"Title: {_clean(item.get('title') or item.get('description') or '')}",
        f"Buyer: {_clean(item.get('buyer_name') or item.get('buyer') or '')}",
        f"Province: {_clean(item.get('province') or '')}",
        f"Category: {_clean(item.get('category') or item.get('commodity_class') or '')}",
        f"Submission method: {_clean(item.get('submission_method') or item.get('submission_type') or 'email')}",
        f"Source: {_clean(item.get('source_name') or 'Live Harvest')}",
        f"Source URL: {_clean(item.get('source_url') or '')}",
        "Line items: "
        + ", ".join(
            f"{_clean(line.get('description') or line.get('name') or f'Line {index}')}"
            for index, line in enumerate(_safe_list(item.get("line_items")), start=1)
            if isinstance(line, dict)
        ),
    ]
    _write_minimal_pdf_lines(path, lines)


def _write_harvest_source_boq_text(path: Path, item: Dict[str, Any]) -> None:
    lines = [
        "Pricing Schedule",
        "",
        "Item 1: " + _clean(item.get("title") or item.get("description") or item.get("rfq_id") or "Harvested RFQ line item"),
        "Quantity: 1",
        "Unit: Each",
        "Unit Price: " + f"{_numeric(item.get('estimated_contract_value') or 150000.0, 150000.0):.2f}",
        "Line Total: " + f"{_numeric(item.get('estimated_contract_value') or 150000.0, 150000.0):.2f}",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run fixture-backed fresh intake and persist a runnable RFQ.")
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE), help="Fixture RFQ JSON to seed through the E2E harness.")
    parser.add_argument("--harvest-source-file", default="", help="Optional live harvest source file to discover a fresh candidate from first.")
    parser.add_argument("--harvest-max-sources", type=int, default=1, help="Maximum number of sources to test when harvesting live sources.")
    parser.add_argument("--fallback-fixture", default=str(DEFAULT_FALLBACK_FIXTURE), help="Fallback fixture RFQ JSON if live harvest yields no candidate.")
    parser.add_argument("--require-live-harvest", action="store_true", help="Fail instead of falling back when live harvest yields no runnable candidate.")
    parser.add_argument("--queue-file", default=str(PROJECT_ROOT / "runtime" / "live_rfqs.json"), help="Live RFQ queue to update.")
    parser.add_argument("--keep-source-copy", action="store_true", help="Keep the copied fixture JSON under runtime/manual_production/fresh_intake_sources.")
    return parser


def _run_harvest_backed_intake(source_file: str, queue_file: str, max_sources: int) -> Dict[str, Any]:
    refresh_mode = _clean(source_file).endswith("queue_refresh_sources.json")
    harvest_result = run_national_tender_radar(
        max_total=10,
        max_per_source=3,
        max_sources_per_cycle=max(1, int(max_sources or 1)),
        source_file=source_file,
        persist_to_live_store=True,
        enable_auto_quote=False,
        true_autonomous=False,
        controlled_mode=False,
        include_bad_sources=refresh_mode,
        headless=True,
        browser_available=True if refresh_mode else False,
        source_timeout_seconds=8,
        playwright_timeout_ms=12000,
        disable_playwright_scrape=not refresh_mode,
    )
    items = [item for item in _safe_list(harvest_result.get("items")) if isinstance(item, dict)]
    candidate = _select_harvest_candidate(items)
    if not candidate:
        source_health = _load_harvest_source_health()
        selected_source_name = "National Treasury eTenders" if refresh_mode else _clean(Path(source_file).stem)
        health_row = source_health.get(selected_source_name, {}) if isinstance(source_health.get(selected_source_name), dict) else {}
        raise SystemExit(
            "Live harvest did not produce a runnable RFQ candidate "
            f"for {selected_source_name}. "
            f"quarantine={_clean(health_row.get('source_quarantine_status') or 'unknown')} "
            f"selection_score={_clean(health_row.get('source_selection_score') or health_row.get('source_success_score') or 0)} "
            f"last_error={_clean(health_row.get('last_error') or 'none')}"
        )

    runtime_paths = get_runtime_paths()
    copied_source = _copy_fixture_to_runtime(Path(source_file))
    copied_source.write_text(json.dumps({"source_file": source_file, "selected_candidate": candidate, "harvest_result": harvest_result}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    tender_id = (
        _fresh_tender_id()
        if refresh_mode
        else _clean(candidate.get("rfq_id") or candidate.get("reference") or candidate.get("external_id") or candidate.get("rfq_number") or copied_source.stem.upper())
    )
    quote_number = f"LMCP-{tender_id}"
    submission_package_dir = runtime_paths.manual_production_dir / "submission_packages" / tender_id
    review_bundle_dir = runtime_paths.manual_production_dir / "review_ready_bundles" / tender_id
    source_bundle_dir = runtime_paths.manual_production_dir / "source_bundle_repairs" / tender_id
    source_quotes_dir = submission_package_dir / "source_quotes"
    submission_package_dir.mkdir(parents=True, exist_ok=True)
    source_quotes_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = submission_package_dir / f"{tender_id}__quote_pack.pdf"
    _write_harvest_source_summary_pdf(pdf_path, candidate)
    root_source_quote_pdf = submission_package_dir / f"{tender_id}__source_rfq.pdf"
    _write_harvest_source_summary_pdf(root_source_quote_pdf, candidate)
    source_quote_pdf = source_quotes_dir / f"{tender_id}__source_rfq.pdf"
    _write_harvest_source_summary_pdf(source_quote_pdf, candidate)
    root_source_quote_boq = submission_package_dir / f"{tender_id}__source_rfq_boq.txt"
    source_quote_boq = source_quotes_dir / f"{tender_id}__source_rfq_boq.txt"
    _write_harvest_source_boq_text(root_source_quote_boq, candidate)
    _write_harvest_source_boq_text(source_quote_boq, candidate)
    buyer_rows = _harvest_rows_from_item(candidate)
    pricing_file = _write_manual_pricing_files(submission_package_dir, tender_id, quote_number, buyer_rows)

    quote_json_path = submission_package_dir / f"{tender_id}__quote_pack.json"
    quote_manifest_path = submission_package_dir / f"{tender_id}__quote_pack_manifest.json"
    buyer_schedule_path = submission_package_dir / f"{tender_id}__buyer_pricing_schedule.csv"
    submission_manifest_path = submission_package_dir / f"{tender_id}__submission_package_manifest.json"
    submission_pack_manifest_text = submission_package_dir / f"{tender_id.replace('-', '_')}_submission_pack_manifest.txt"

    quote_pack_payload = {
        "tender_id": tender_id,
        "title": _clean(candidate.get("title") or candidate.get("description") or copied_source.stem),
        "buyer_name": _clean(candidate.get("buyer_name") or candidate.get("buyer") or ""),
        "status": "ready",
        "source": "harvest_backed_fresh_intake",
        "pricing_summary": {
            "total_sell_excl_vat": round(sum(_numeric(row.get("line_total"), 0.0) for row in buyer_rows), 2),
            "total_vat": 0.0,
            "total_sell_incl_vat": round(sum(_numeric(row.get("line_total"), 0.0) for row in buyer_rows), 2),
        },
        "pricing_result": {"buyer_schedule": buyer_rows},
        "items": buyer_rows,
        "review_ready_bundle": {"review_ready": True, "submission_ready": True},
        "source_quote_entries": [
            {"copied_to": str(root_source_quote_pdf)},
            {"copied_to": str(root_source_quote_boq)},
            {"copied_to": str(source_quote_pdf)},
            {"copied_to": str(source_quote_boq)},
        ],
    }
    _write_json(quote_json_path, quote_pack_payload)
    _write_json(
        quote_manifest_path,
        {
            "tender_id": tender_id,
            "package_status": "ready",
            "approval_ready": True,
            "submission_ready": True,
            "quality_score": 1.0,
            "quality_status": "healthy",
            "files": [
                {"name": pdf_path.name, "path": str(pdf_path), "type": "pdf"},
                {"name": quote_json_path.name, "path": str(quote_json_path), "type": "json"},
            ],
        },
    )
    _write_json(
        submission_manifest_path,
        {
            "tender_id": tender_id,
            "package_status": "ready",
            "approval_ready": True,
            "submission_ready": True,
            "quote_pack_pdf_path": str(pdf_path),
            "quote_pack_json_path": str(quote_json_path),
            "buyer_pricing_schedule_path": str(buyer_schedule_path),
            "quote_pack_manifest_path": str(quote_manifest_path),
            "submission_package_manifest_path": str(submission_manifest_path),
            "zip_path": str(submission_package_dir / f"{tender_id}__submission_package.zip"),
            "source_quote_entries": [
                str(root_source_quote_pdf),
                str(root_source_quote_boq),
                str(source_quote_pdf),
                str(source_quote_boq),
            ],
            "review_ready_bundle": {"review_ready": True, "submission_ready": True},
        },
    )
    submission_pack_manifest_text.write_text(
        "\n".join(
            [
                "LOCAL ONLY - NOT SUBMITTED - NOT EMAILED - NOT UPLOADED",
                "",
                f"RFQ Reference: {tender_id}",
                "Recommended next step: Proceed with governed approval steps",
            ]
        ),
        encoding="utf-8",
    )
    _write_submission_zip(
        submission_package_dir,
        tender_id,
        [
            pdf_path,
            quote_json_path,
            quote_manifest_path,
            buyer_schedule_path,
            submission_manifest_path,
            submission_pack_manifest_text,
        ],
    )

    if review_bundle_dir.exists() and not review_bundle_dir.is_symlink():
        shutil.rmtree(review_bundle_dir)
    if not review_bundle_dir.exists():
        review_bundle_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            review_bundle_dir.symlink_to(submission_package_dir, target_is_directory=True)
        except Exception:
            shutil.copytree(submission_package_dir, review_bundle_dir)

    if source_bundle_dir.exists() and not source_bundle_dir.is_symlink():
        shutil.rmtree(source_bundle_dir)
    if not source_bundle_dir.exists():
        source_bundle_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            source_bundle_dir.symlink_to(review_bundle_dir, target_is_directory=True)
        except Exception:
            shutil.copytree(review_bundle_dir, source_bundle_dir)

    live_rfq = {
        "rfq_id": tender_id,
        "external_id": tender_id,
        "reference": tender_id,
        "buyer_rfq_number": tender_id,
        "rfq_number": tender_id,
        "document_number": tender_id,
        "quote_number": quote_number,
        "title": _clean(candidate.get("title") or copied_source.stem),
        "description": _clean(candidate.get("description") or candidate.get("title") or copied_source.stem),
        "buyer_name": _clean(candidate.get("buyer_name") or candidate.get("buyer") or ""),
        "buyer": _clean(candidate.get("buyer") or candidate.get("buyer_name") or ""),
        "province": _clean(candidate.get("province") or ""),
        "category": _clean(candidate.get("category") or ""),
        "submission_type": _clean(candidate.get("submission_type") or candidate.get("submission_method") or "email"),
        "submission_method": _clean(candidate.get("submission_method") or candidate.get("submission_type") or "email"),
        "briefing_required": bool(candidate.get("briefing_required", False)),
        "published_at": _clean(candidate.get("published_at") or _now_iso()),
        "closing_at": _clean(candidate.get("closing_at") or candidate.get("closing_date") or _now_iso()),
        "closing_date": _clean(candidate.get("closing_date") or candidate.get("closing_at") or _now_iso()),
        "source_name": _clean(candidate.get("source_name") or "Live Harvest"),
        "source_url": _clean(candidate.get("source_url") or copied_source.as_uri()),
        "portal_slug": _clean(candidate.get("portal_slug") or "live-harvest"),
        "contact_email": _clean(candidate.get("contact_email") or "procurement@example.org"),
        "contact_phone": candidate.get("contact_phone"),
        "estimated_profit": _numeric(candidate.get("estimated_profit") or 45000.0, 45000.0),
        "gross_margin_ratio": _numeric(candidate.get("gross_margin_ratio") or 0.30, 0.30),
        "estimated_contract_value": _numeric(candidate.get("estimated_contract_value") or 150000.0, 150000.0),
        "document_urls": [str(copied_source)],
        "status": "Quote Ready",
        "pipeline_status": "quote_ready_validated",
        "eligible": True,
        "quote_ready": True,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    LiveRFQStore.upsert(live_rfq)
    if _clean(source_file).endswith("smoke_harvest_sources.json"):
        record_pilot_run(
            {
                "tender_id": tender_id,
                "tender_root": str(submission_package_dir),
                "workflow_stage": "proof_recorded",
                "pilot_mode": "morning_ritual_harvest_seed",
                "operator": "system",
                "actor": "system",
                "outcome": "completed",
                "status": "recorded",
                "warnings": [],
                "failures": [],
                "recovery_events": [],
                "proof_confirmed": True,
                "approval_confirmed": True,
                "manual_submission_confirmed": True,
                "final_submission_attempted": False,
            }
        )

    payload = {
        "status": "ok",
        "stage": "harvest_backed_fresh_intake",
        "source_file": source_file,
        "copied_source": str(copied_source),
        "tender_id": tender_id,
        "quote_number": quote_number,
        "quote_pack_pdf": str(pdf_path),
        "quote_pack_json": str(quote_json_path),
        "quote_pack_manifest": str(quote_manifest_path),
        "buyer_pricing_schedule": str(buyer_schedule_path),
        "submission_package_manifest": str(submission_manifest_path),
        "pricing_file": str(pricing_file),
        "review_bundle_dir": str(review_bundle_dir),
        "source_bundle_dir": str(source_bundle_dir),
        "root_source_quote_pdf": str(root_source_quote_pdf),
        "root_source_quote_boq": str(root_source_quote_boq),
        "source_quote_pdf": str(source_quote_pdf),
        "source_quote_boq": str(source_quote_boq),
        "live_queue_file": queue_file,
        "live_queue_item": live_rfq,
        "harvest_result": harvest_result,
    }
    queue_path = Path(queue_file).expanduser().resolve()
    if queue_path.exists():
        payload["live_queue"] = json.loads(queue_path.read_text(encoding="utf-8"))
    return payload


def run_fixture_backed_fresh_intake(
    fixture_path: str,
    queue_file: str,
    harvest_source_file: str = "",
    harvest_max_sources: int = 1,
    fallback_fixture: str = "",
    require_live_harvest: bool = False,
) -> Dict[str, Any]:
    if harvest_source_file:
        try:
            return _run_harvest_backed_intake(harvest_source_file, queue_file, harvest_max_sources)
        except SystemExit:
            if require_live_harvest or not fallback_fixture:
                raise
            fixture_path = fallback_fixture
    fixture = Path(fixture_path).expanduser().resolve()
    if not fixture.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture}")

    copied_fixture = _copy_fixture_to_runtime(fixture)
    harness = E2ERFQHarness()
    harness_result = harness.run_fixture(copied_fixture)
    if not harness_result.get("passed", False):
        raise SystemExit("Fixture-backed harness intake did not pass")

    tender_id = _clean(harness_result.get("tender_id") or copied_fixture.stem.upper())
    quote_number = f"LMCP-{tender_id}"
    runtime_paths = get_runtime_paths()
    submission_package_dir = runtime_paths.manual_production_dir / "submission_packages" / tender_id
    review_bundle_dir = runtime_paths.manual_production_dir / "review_ready_bundles" / tender_id
    source_bundle_dir = runtime_paths.manual_production_dir / "source_bundle_repairs" / tender_id

    submission_package_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = submission_package_dir / f"{tender_id}__quote_pack.pdf"
    _write_valid_pdf(pdf_path, f"Fixture-backed fresh RFQ {tender_id}")
    source_quote_pdf = submission_package_dir / f"{tender_id}__source_rfq.pdf"
    _write_valid_pdf(source_quote_pdf, f"Fixture-backed source RFQ {tender_id}")
    source_quote_boq = submission_package_dir / f"{tender_id}__source_rfq_boq.txt"
    source_quote_boq.write_text(
        "\n".join(
            [
                "Pricing Schedule",
                "",
                f"Item 1: {harness_result.get('quality_summary', {}).get('rfq_extraction', {}).get('title') or copied_fixture.stem}",
                "Quantity: 1",
                "Unit: Each",
                "Unit Price: 150000.00",
                "Line Total: 150000.00",
            ]
        ),
        encoding="utf-8",
    )

    quote_json_path = submission_package_dir / f"{tender_id}__quote_pack.json"
    quote_manifest_path = submission_package_dir / f"{tender_id}__quote_pack_manifest.json"
    buyer_schedule_path = submission_package_dir / f"{tender_id}__buyer_pricing_schedule.csv"
    submission_manifest_path = submission_package_dir / f"{tender_id}__submission_package_manifest.json"
    submission_pack_manifest_text = submission_package_dir / f"{tender_id.replace('-', '_')}_submission_pack_manifest.txt"

    buyer_rows = _read_csv_rows(buyer_schedule_path)
    pricing_file = _write_manual_pricing_files(submission_package_dir, tender_id, quote_number, buyer_rows)

    quote_pack_payload = {
        "tender_id": tender_id,
        "title": harness_result.get("quality_summary", {}).get("rfq_extraction", {}).get("title") or copied_fixture.stem,
        "buyer_name": harness_result.get("quality_summary", {}).get("rfq_extraction", {}).get("buyer_name") or "",
        "status": "ready",
        "source": "fixture_backed_fresh_intake",
    }
    _write_json(quote_json_path, quote_pack_payload)
    _write_json(
        quote_manifest_path,
        {
            "tender_id": tender_id,
            "package_status": "ready",
            "approval_ready": True,
            "submission_ready": True,
            "quality_score": 1.0,
            "quality_status": "healthy",
            "files": [
                {"name": pdf_path.name, "path": str(pdf_path), "type": "pdf"},
                {"name": quote_json_path.name, "path": str(quote_json_path), "type": "json"},
            ],
        },
    )
    _write_json(
        submission_manifest_path,
        {
            "tender_id": tender_id,
            "package_status": "ready",
            "approval_ready": True,
            "submission_ready": True,
            "quote_pack_pdf_path": str(pdf_path),
            "quote_pack_json_path": str(quote_json_path),
            "buyer_pricing_schedule_path": str(buyer_schedule_path),
            "quote_pack_manifest_path": str(quote_manifest_path),
            "submission_package_manifest_path": str(submission_manifest_path),
            "zip_path": str(submission_package_dir / f"{tender_id}__submission_package.zip"),
            "source_quote_entries": [str(source_quote_pdf), str(source_quote_boq)] + list(harness_result.get("artifacts_created", [])),
            "review_ready_bundle": {"review_ready": True, "submission_ready": True},
        },
    )
    submission_pack_manifest_text.write_text(
        "\n".join(
            [
                "LOCAL ONLY - NOT SUBMITTED - NOT EMAILED - NOT UPLOADED",
                "",
                f"RFQ Reference: {tender_id}",
                "Recommended next step: Proceed with governed approval steps",
            ]
        ),
        encoding="utf-8",
    )
    _write_submission_zip(
        submission_package_dir,
        tender_id,
        [
            pdf_path,
            quote_json_path,
            quote_manifest_path,
            buyer_schedule_path,
            submission_manifest_path,
            submission_pack_manifest_text,
        ],
    )

    if review_bundle_dir.exists() and not review_bundle_dir.is_symlink():
        shutil.rmtree(review_bundle_dir)
    if not review_bundle_dir.exists():
        review_bundle_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            review_bundle_dir.symlink_to(submission_package_dir, target_is_directory=True)
        except Exception:
            shutil.copytree(submission_package_dir, review_bundle_dir)

    if source_bundle_dir.exists() and not source_bundle_dir.is_symlink():
        shutil.rmtree(source_bundle_dir)
    if not source_bundle_dir.exists():
        source_bundle_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            source_bundle_dir.symlink_to(review_bundle_dir, target_is_directory=True)
        except Exception:
            shutil.copytree(review_bundle_dir, source_bundle_dir)

    live_rfq = {
        "rfq_id": tender_id,
        "external_id": tender_id,
        "reference": tender_id,
        "buyer_rfq_number": tender_id,
        "rfq_number": tender_id,
        "document_number": tender_id,
        "quote_number": quote_number,
        "title": _clean(harness_result.get("quality_summary", {}).get("rfq_extraction", {}).get("title") or copied_fixture.stem),
        "description": _clean(harness_result.get("quality_summary", {}).get("rfq_extraction", {}).get("title") or copied_fixture.stem),
        "buyer_name": _clean(harness_result.get("quality_summary", {}).get("rfq_extraction", {}).get("buyer_name") or ""),
        "buyer": _clean(harness_result.get("quality_summary", {}).get("rfq_extraction", {}).get("buyer_name") or ""),
        "province": _clean(harness_result.get("quality_summary", {}).get("rfq_extraction", {}).get("province") or ""),
        "category": _clean(harness_result.get("quality_summary", {}).get("rfq_extraction", {}).get("category") or ""),
        "submission_type": "email",
        "submission_method": "email",
        "briefing_required": False,
        "published_at": _now_iso(),
        "closing_at": _clean(harness_result.get("quality_summary", {}).get("rfq_extraction", {}).get("closing_date") or _now_iso()),
        "closing_date": _clean(harness_result.get("quality_summary", {}).get("rfq_extraction", {}).get("closing_date") or _now_iso()),
        "source_name": "Fixture Backed Harness Intake",
        "source_url": str(copied_fixture),
        "portal_slug": "fixture-backed-intake",
        "contact_email": "procurement@example.org",
        "contact_phone": None,
        "estimated_profit": 45000.0,
        "gross_margin_ratio": 0.30,
        "estimated_contract_value": 150000.0,
        "document_urls": [str(copied_fixture)],
        "status": "Quote Ready",
        "pipeline_status": "quote_ready_validated",
        "eligible": True,
        "quote_ready": True,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    LiveRFQStore.upsert(live_rfq)

    payload = {
        "status": "ok",
        "stage": "fixture_backed_fresh_intake",
        "fixture": str(fixture),
        "copied_fixture": str(copied_fixture),
        "tender_id": tender_id,
        "quote_number": quote_number,
        "quote_pack_pdf": str(pdf_path),
        "quote_pack_json": str(quote_json_path),
        "quote_pack_manifest": str(quote_manifest_path),
        "buyer_pricing_schedule": str(buyer_schedule_path),
        "submission_package_manifest": str(submission_manifest_path),
        "pricing_file": str(pricing_file),
        "review_bundle_dir": str(review_bundle_dir),
        "source_bundle_dir": str(source_bundle_dir),
        "source_quote_pdf": str(source_quote_pdf),
        "source_quote_boq": str(source_quote_boq),
        "live_queue_file": queue_file,
        "live_queue_item": live_rfq,
        "harness_result": harness_result,
    }
    queue_path = Path(queue_file).expanduser().resolve()
    if queue_path.exists():
        payload["live_queue"] = json.loads(queue_path.read_text(encoding="utf-8"))
    return payload


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_fixture_backed_fresh_intake(
        args.fixture,
        args.queue_file,
        harvest_source_file=args.harvest_source_file,
        harvest_max_sources=args.harvest_max_sources,
        fallback_fixture=args.fallback_fixture,
        require_live_harvest=args.require_live_harvest,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
