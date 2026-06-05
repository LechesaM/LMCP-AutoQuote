from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs" / "business_assets"
DATASETS_DIR = OUT_DIR / "datasets"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def stable_id(*parts: str) -> str:
    joined = "||".join(parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def slug(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return value or "record"


def read_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            records.append(json.loads(raw))
    return records


def collapse_source_quote_name(filename: str) -> str:
    stem = re.sub(r"\.[^.]+$", "", filename)
    stem = re.sub(r"_(\d{1,2})_.*$", "", stem)
    return stem.strip()


def has_placeholder(value) -> bool:
    if isinstance(value, str):
        return "placeholder" in value.lower()
    if isinstance(value, list):
        return any(has_placeholder(item) for item in value)
    if isinstance(value, dict):
        return any(has_placeholder(item) for item in value.values())
    return False


def yaml_escape(value: str) -> str:
    if value == "":
        return '""'
    if re.fullmatch(r"[A-Za-z0-9 _.,:/()+\-?]+", value) and ": " not in value and not value.startswith((" ", "-", "{", "[")) and not value.endswith(" "):
        return value
    return json.dumps(value)


def to_yaml_lines(value, indent: int = 0) -> list[str]:
    space = " " * indent
    if isinstance(value, list):
        if not value:
            return [f"{space}[]"]
        lines: list[str] = []
        for item in value:
            if isinstance(item, (dict, list)):
                nested = to_yaml_lines(item, indent + 2)
                lines.append(f"{space}- {nested[0].lstrip()}")
                lines.extend(nested[1:])
            else:
                lines.append(f"{space}- {yaml_escape(str(item))}")
        return lines
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{space}{key}:")
                lines.extend(to_yaml_lines(item, indent + 2))
            else:
                lines.append(f"{space}{key}: {yaml_escape(str(item))}")
        return lines
    return [f"{space}{yaml_escape(str(value))}"]


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def write_yaml(path: Path, payload) -> None:
    path.write_text("\n".join(to_yaml_lines(payload)) + "\n", encoding="utf-8")


def validate_json(path: Path) -> dict:
    json.loads(path.read_text(encoding="utf-8"))
    return {"ok": True, "path": rel(path)}


def validate_yaml(path: Path) -> dict:
    command = ["ruby", "-e", "require 'yaml'; YAML.load_file(ARGV[0])", str(path)]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    return {
        "ok": completed.returncode == 0,
        "path": rel(path),
        "stderr": completed.stderr.strip(),
    }


def collect_rfq_gold() -> list[dict]:
    records: list[dict] = []

    fixture_paths = sorted((ROOT / "tests" / "fixtures").glob("**/*.json"))
    for path in fixture_paths:
        data = read_json(path)
        if not isinstance(data, dict):
            continue
        tender_id = data.get("tender_id") or data.get("rfq_number") or data.get("title") or path.stem
        records.append(
            {
                "scenario_id": stable_id("rfq", rel(path), str(tender_id)),
                "scenario_type": "fixture",
                "tender_id": tender_id,
                "title": data.get("title", ""),
                "buyer_name": data.get("buyer_name", ""),
                "province": data.get("province", ""),
                "category": data.get("category", ""),
                "source_path": rel(path),
                "source_family": path.parent.name,
                "line_item_count": len(data.get("line_items", [])),
                "pricing_file": data.get("pricing_file", ""),
                "expected_exclusion_status": data.get("expected_exclusion_status", ""),
                "expected_submission_ready": data.get("expected_submission_ready"),
                "evidence_grade": "high",
            }
        )

    report_paths = sorted((ROOT / "runtime" / "rfq_document_intelligence" / "reports").glob("*.json"))
    for path in report_paths:
        data = read_json(path)
        intelligence = data.get("document_intelligence", {})
        tender_id = data.get("buyer_rfq_number") or data.get("title") or path.stem
        records.append(
            {
                "scenario_id": stable_id("rfq", rel(path), str(tender_id)),
                "scenario_type": "document_intelligence_report",
                "tender_id": tender_id,
                "title": data.get("title", ""),
                "buyer_name": data.get("buyer_name", ""),
                "province": "",
                "category": "",
                "source_path": rel(path),
                "source_family": "runtime_report",
                "line_item_count": len(intelligence.get("quantity_mentions", [])),
                "pricing_schedule_detected": intelligence.get("has_pricing_schedule", False),
                "pricing_schedule_confidence": intelligence.get("pricing_schedule_confidence", 0.0),
                "extraction_confidence": intelligence.get("extraction_confidence", 0.0),
                "evidence_grade": "medium",
            }
        )

    live_rfqs = read_json(ROOT / "runtime" / "live_rfqs.json")
    for item in live_rfqs.get("items", []):
        tender_id = item.get("rfq_number") or item.get("rfq_id") or item.get("title")
        records.append(
            {
                "scenario_id": stable_id("rfq", "live_rfqs", str(tender_id)),
                "scenario_type": "live_rfq",
                "tender_id": tender_id,
                "title": item.get("title", ""),
                "buyer_name": item.get("buyer_name", ""),
                "province": item.get("province", ""),
                "category": item.get("category", ""),
                "source_path": rel(ROOT / "runtime" / "live_rfqs.json"),
                "source_family": "live_rfqs",
                "line_item_count": len(item.get("items", []) or item.get("line_items", [])),
                "eligible": item.get("eligible"),
                "pipeline_status": item.get("pipeline_status", ""),
                "document_verification_status": item.get("document_verification_status", ""),
                "evidence_grade": "high",
            }
        )

    rfq_lifecycle = read_json(ROOT / "runtime" / "rfq_lifecycle" / "rfqs.json")
    for key, item in sorted((rfq_lifecycle.get("items") or {}).items()):
        tender_id = item.get("rfq_number") or item.get("rfq_id") or item.get("title") or key
        records.append(
            {
                "scenario_id": stable_id("rfq", "rfq_lifecycle", str(tender_id)),
                "scenario_type": "rfq_lifecycle_snapshot",
                "tender_id": tender_id,
                "title": item.get("title", ""),
                "buyer_name": item.get("buyer_name", ""),
                "province": item.get("province", ""),
                "category": item.get("category", ""),
                "source_path": rel(ROOT / "runtime" / "rfq_lifecycle" / "rfqs.json"),
                "source_family": "rfq_lifecycle",
                "line_item_count": len(item.get("items", []) or item.get("documents", [])),
                "eligible": item.get("eligible"),
                "validation_status": item.get("validation_status", ""),
                "quote_ready": item.get("quote_ready"),
                "evidence_grade": "high",
            }
        )

    e2e_paths = sorted((ROOT / "runtime").glob("tmp_e2e_*/*.json")) + sorted((ROOT / "runtime" / "e2e_fixtures").glob("*.json"))
    for path in e2e_paths:
        data = read_json(path)
        if not isinstance(data, dict):
            continue
        tender_id = data.get("tender_id") or data.get("rfq_number") or data.get("title") or path.stem
        records.append(
            {
                "scenario_id": stable_id("rfq", rel(path), str(tender_id)),
                "scenario_type": "e2e_fixture",
                "tender_id": tender_id,
                "title": data.get("title", ""),
                "buyer_name": data.get("buyer_name", ""),
                "province": data.get("province", ""),
                "category": data.get("category", ""),
                "source_path": rel(path),
                "source_family": path.parent.name,
                "line_item_count": len(data.get("line_items", [])),
                "submission_type": data.get("submission_type", ""),
                "evidence_grade": "medium",
            }
        )

    bundle_paths = sorted((ROOT / "runtime" / "manual_production" / "review_ready_bundles").glob("*/review_ready_quote_pack.json"))
    for path in bundle_paths:
        data = read_json(path)
        tender_id = data.get("tender_id") or path.parent.name
        live_rfq = data.get("live_rfq", {})
        records.append(
            {
                "scenario_id": stable_id("rfq", rel(path), str(tender_id)),
                "scenario_type": "review_ready_bundle",
                "tender_id": tender_id,
                "title": live_rfq.get("title", ""),
                "buyer_name": live_rfq.get("buyer", ""),
                "province": "",
                "category": "",
                "source_path": rel(path),
                "source_family": "review_ready_bundle",
                "line_item_count": len(live_rfq.get("items", [])),
                "review_ready": data.get("review_ready"),
                "submission_ready": data.get("submission_ready"),
                "bundle_status": data.get("bundle_status", ""),
                "evidence_grade": "high",
            }
        )

    return sorted(records, key=lambda record: (record["tender_id"], record["scenario_type"], record["source_path"]))


def collect_supplier_intelligence(limit: int = 110) -> list[dict]:
    candidates: dict[str, dict] = {}
    banned_terms = [
        "placeholder",
        "message-id",
        "date:",
        "sent:",
        " wrote",
        "would like to recall",
        "footer",
        "template",
        "cta_",
    ]
    banned_exact = {
        ", and without",
        "doing business with the",
        "doing business with the public sector?",
        "the company but it",
        "the shareholder whether to exercise, or",
        "name",
    }

    def add_candidate(name: str, source_path: Path, source_type: str, quality: str, **extra) -> None:
        value = (name or "").strip()
        if len(value) < 6:
            return
        lowered = value.lower()
        if lowered in banned_exact:
            return
        if any(term in lowered for term in banned_terms):
            return
        score = {"high": 3, "medium": 2, "low": 1}[quality]
        record = {
            "supplier_id": stable_id("supplier", value, rel(source_path), source_type),
            "supplier_reference": value,
            "supplier_slug": slug(value),
            "normalization_status": "raw_source_reference",
            "source_type": source_type,
            "source_path": rel(source_path),
            "evidence_grade": quality,
            "quality_rank": score,
            **extra,
        }
        best = candidates.get(value)
        if best is None or record["quality_rank"] > best["quality_rank"]:
            candidates[value] = record

    review_bundle_paths = sorted((ROOT / "runtime" / "manual_production" / "review_ready_bundles").glob("*/review_ready_quote_pack.json"))
    for path in review_bundle_paths:
        data = read_json(path)
        for quote in ((data.get("quote_comparison") or {}).get("supplier_quotes") or []):
            add_candidate(
                quote.get("supplier_name", ""),
                path,
                "review_ready_quote_comparison",
                "high",
                quote_number=quote.get("quote_number", ""),
                total_incl_vat=quote.get("total_incl_vat"),
                extraction_confidence=quote.get("extraction_confidence"),
                compliant=quote.get("compliant"),
            )

    tender_quote_paths = sorted((ROOT / "runtime" / "tender_submission_pipeline").glob("*/*quote_pack.json"))
    for path in tender_quote_paths:
        data = read_json(path)
        for row in data.get("rows", []):
            add_candidate(
                row.get("supplier_name", ""),
                path,
                "tender_quote_pack",
                "high",
                quote_number=row.get("supplier_quote_ref", ""),
                unit_price=row.get("unit_price"),
                line_total=row.get("line_total"),
            )

    for path in sorted((ROOT / "runtime" / "quote_compilation").glob("**/pricing_schedule_completed.json")):
        data = read_json(path)
        for item in data.get("items", []):
            add_candidate(
                item.get("supplier_name", ""),
                path,
                "quote_compilation_schedule",
                "high",
                quote_number=item.get("supplier_quote_ref", ""),
                unit_price=item.get("unit_price"),
                line_total=item.get("line_total"),
            )

    for path in sorted((ROOT / "runtime" / "supplier_quote_intelligence").glob("**/pipeline_summary.json")):
        data = read_json(path)
        for quote in data.get("supplier_quotes", []):
            add_candidate(
                quote.get("supplier_name", ""),
                path,
                "supplier_quote_pipeline",
                "medium",
                quote_number=quote.get("quote_reference", ""),
                total_incl_vat=quote.get("total_incl_vat"),
                extraction_confidence=quote.get("extraction_confidence") or quote.get("confidence"),
            )

    for path in sorted((ROOT / "runtime").glob("**/*.json")):
        if "audit_trail" in str(path):
            continue
        try:
            data = read_json(path)
        except Exception:
            continue

        def walk_company_names(value) -> None:
            if isinstance(value, dict):
                company_name = value.get("company_name")
                if isinstance(company_name, str):
                    add_candidate(
                        company_name,
                        path,
                        "company_name_capture",
                        "medium",
                    )
                for child in value.values():
                    walk_company_names(child)
            elif isinstance(value, list):
                for child in value:
                    walk_company_names(child)

        walk_company_names(data)

    for path in sorted((ROOT / "runtime" / "manual_production" / "submission_packages").glob("*/source_quotes/*")):
        entity = collapse_source_quote_name(path.name)
        add_candidate(
            entity,
            path,
            "submission_package_source_quote",
            "medium",
            file_extension=path.suffix.lower(),
        )

    records = sorted(
        candidates.values(),
        key=lambda record: (-record["quality_rank"], record["supplier_reference"], record["source_path"]),
    )
    return records[:limit]


def collect_pricing_intelligence(limit: int = 360) -> list[dict]:
    candidates: list[dict] = []
    seen: set[str] = set()
    banned_desc = ["placeholder", "message-id", "date:", "sent:", " wrote", "would like to recall"]

    def valid_description(text: str) -> bool:
        lowered = (text or "").strip().lower()
        if not lowered:
            return False
        return not any(term in lowered for term in banned_desc)

    def add_record(source_path: Path, source_type: str, description: str, quantity, unit, unit_price, line_total, supplier_name="", confidence=None, rfq_reference="", quality="medium", line_ref="") -> None:
        if not valid_description(description):
            return
        try:
            price_value = float(unit_price or 0)
        except (TypeError, ValueError):
            price_value = 0.0
        try:
            total_value = float(line_total or 0)
        except (TypeError, ValueError):
            total_value = 0.0
        if price_value <= 0 and total_value <= 0:
            return
        fingerprint = stable_id(rel(source_path), source_type, str(line_ref), description, str(price_value), str(total_value))
        if fingerprint in seen:
            return
        seen.add(fingerprint)
        quality_rank = {"high": 3, "medium": 2, "low": 1}[quality]
        candidates.append(
            {
                "pricing_line_id": fingerprint,
                "source_type": source_type,
                "source_path": rel(source_path),
                "rfq_reference": rfq_reference,
                "description": description.strip(),
                "quantity": quantity,
                "unit": unit,
                "unit_price": price_value,
                "line_total": total_value,
                "supplier_name": supplier_name,
                "extraction_confidence": confidence,
                "evidence_grade": quality,
                "quality_rank": quality_rank,
            }
        )

    for path in sorted((ROOT / "runtime" / "tender_submission_pipeline").glob("*/*quote_pack.json")):
        data = read_json(path)
        rows = data.get("rows", [])
        rfq_reference = (data.get("final_output") or {}).get("rfq_number") or data.get("rfq_reference") or data.get("pack_id") or path.parent.name
        for row in rows:
            add_record(
                path,
                "tender_quote_pack",
                row.get("description", ""),
                row.get("quantity"),
                row.get("unit"),
                row.get("unit_price"),
                row.get("line_total"),
                supplier_name=row.get("supplier_name", ""),
                confidence=1.0,
                rfq_reference=rfq_reference,
                quality="high",
                line_ref=str(row.get("output_row_number") or row.get("item_number") or row.get("description")),
            )

    for path in sorted((ROOT / "runtime" / "quote_compilation").glob("**/pricing_schedule_completed.json")):
        data = read_json(path)
        items = data.get("items", [])
        rfq_reference = data.get("rfq_reference") or data.get("pack_id") or path.parent.name
        for item in items:
            add_record(
                path,
                "quote_compilation_schedule",
                item.get("description", ""),
                item.get("quantity"),
                item.get("unit"),
                item.get("unit_price_ex_vat") or item.get("unit_cost"),
                item.get("total_inc_vat") or item.get("total_ex_vat"),
                supplier_name="",
                confidence=0.95,
                rfq_reference=rfq_reference,
                quality="high",
                line_ref=str(item.get("line_no") or item.get("description")),
            )

    for path in sorted((ROOT / "runtime" / "supplier_quote_intelligence").glob("**/pipeline_summary.json")):
        data = read_json(path)
        for quote in data.get("supplier_quotes", []):
            supplier_name = quote.get("supplier_name", "")
            rfq_reference = quote.get("quote_reference") or quote.get("reference") or path.parent.name
            for item in quote.get("line_items", []) or quote.get("items", []):
                add_record(
                    path,
                    "supplier_quote_pipeline",
                    item.get("description", ""),
                    item.get("quantity"),
                    item.get("unit"),
                    item.get("unit_price"),
                    item.get("line_total"),
                    supplier_name=supplier_name,
                    confidence=item.get("confidence"),
                    rfq_reference=rfq_reference,
                    quality="medium",
                    line_ref=str(item.get("line_no") or item.get("description")),
                )

    candidates.sort(key=lambda record: (-record["quality_rank"], record["source_path"], record["description"]))
    return candidates[:limit]


def collect_tender_win_intelligence(limit: int = 120) -> list[dict]:
    records: list[dict] = []
    selected_json_files = [
        ROOT / "runtime" / "submission_history" / "submission_history.json",
        ROOT / "runtime" / "submission_history" / "v47_portal_submission_history.json",
        ROOT / "runtime" / "final_submission_v47_5" / "final_submission_history.json",
        ROOT / "runtime" / "manual_production" / "external_audit_exports" / "REAL-PILOT-001" / "REAL-PILOT-001__submission_history.json",
    ]

    for path in selected_json_files:
        data = read_json(path)
        if not isinstance(data, list):
            continue
        for index, item in enumerate(data, start=1):
            tender_id = item.get("tender_id") or item.get("buyer_rfq_number") or item.get("quote_number") or path.parent.name
            status = item.get("status", "")
            provenance_type = "Submission Outcome"
            if "final_submission_history" in path.name:
                provenance_type = "Internal Intelligence"
            records.append(
                {
                    "record_id": stable_id("tender-win", rel(path), str(index), str(tender_id), status),
                    "record_class": "submission_history",
                    "tender_id": tender_id,
                    "buyer_name": item.get("buyer_name", ""),
                    "status": status,
                    "event_at": item.get("submitted_at") or item.get("completed_at") or item.get("created_at") or "",
                    "source_path": rel(path),
                    "source_type": path.name,
                    "provenance_type": provenance_type,
                    "evidence_grade": "high",
                }
            )

    jsonl_paths = sorted((ROOT / "runtime" / "manual_production").glob("**/*.jsonl"))
    keep_fragments = [
        "submission_execution_history",
        "governance_decision_history",
        "submission_proofs.jsonl",
        "submission_reviews.jsonl",
        "approvals.jsonl",
    ]
    for path in jsonl_paths:
        if not any(fragment in str(path) for fragment in keep_fragments):
            continue
        for index, item in enumerate(read_jsonl(path), start=1):
            tender_id = item.get("tender_id") or item.get("pack_id") or item.get("buyer_rfq_number") or item.get("submission_reference") or path.parent.name
            status = item.get("status") or item.get("decision") or item.get("action") or item.get("state") or ""
            provenance_type = "Derived Signal"
            if "submission_execution_history" in str(path) or "submission_proofs.jsonl" in str(path):
                provenance_type = "Submission Outcome"
            elif "governance_decision_history" in str(path) or "submission_reviews.jsonl" in str(path) or "approvals.jsonl" in str(path):
                provenance_type = "Internal Intelligence"
            records.append(
                {
                    "record_id": stable_id("tender-win", rel(path), str(index), str(tender_id), str(status)),
                    "record_class": "governed_outcome_event",
                    "tender_id": tender_id,
                    "buyer_name": item.get("buyer_name", ""),
                    "status": status,
                    "event_at": item.get("submitted_at") or item.get("completed_at") or item.get("created_at") or item.get("timestamp") or "",
                    "source_path": rel(path),
                    "source_type": path.name,
                    "provenance_type": provenance_type,
                    "evidence_grade": "medium",
                }
            )

    records.sort(key=lambda record: (record["event_at"], record["source_path"], record["record_id"]), reverse=True)
    return records[:limit]


def validate_dataset(name: str, records: list[dict]) -> dict:
    source_paths = {record["source_path"] for record in records}
    placeholder_count = sum(1 for record in records if has_placeholder(record))
    missing_sources = [path for path in source_paths if not (ROOT / path).exists()]
    return {
        "dataset": name,
        "record_count": len(records),
        "source_count": len(source_paths),
        "placeholder_records": placeholder_count,
        "missing_source_paths": missing_sources,
        "ok": placeholder_count == 0 and not missing_sources,
    }


def write_readme(summary: dict) -> None:
    lines = [
        "# Business Intelligence Expansion Pack",
        "",
        "## Purpose",
        "This pack assembles evidence-backed non-runtime business-intelligence assets from local repo artifacts only.",
        "",
        "## Scope",
        "- Advisory data only.",
        "- No execution-layer changes.",
        "- No workflow-control changes.",
        "- No runtime recertification actions.",
        "",
        "## Dataset Counts",
        f"- RFQ Gold Dataset scenarios: {summary['datasets']['rfq_gold_dataset']['record_count']}",
        f"- Supplier Intelligence records: {summary['datasets']['supplier_intelligence']['record_count']}",
        f"- Pricing Intelligence lines: {summary['datasets']['pricing_intelligence']['record_count']}",
        f"- Tender-Win Intelligence records: {summary['datasets']['tender_win_intelligence']['record_count']}",
        "",
        "## Governance Note",
        "Tender-win records in this pack are drawn from local governed submission and outcome evidence. They are useful intelligence inputs, but they are not promoted here as external award confirmations.",
        "",
        "## Validation",
        f"- JSON index validated: {summary['validation']['json_index']['ok']}",
        f"- YAML index validated: {summary['validation']['yaml_index']['ok']}",
        f"- Placeholder scan passed: {summary['validation']['placeholder_scan_passed']}",
        f"- Evidence-path check passed: {summary['validation']['source_path_check_passed']}",
        "",
        "## Files",
        "- `datasets/rfq_gold_dataset.jsonl`",
        "- `datasets/supplier_intelligence.jsonl`",
        "- `datasets/pricing_intelligence.jsonl`",
        "- `datasets/tender_win_intelligence.jsonl`",
        "- `index.json`",
        "- `index.yaml`",
        "- `consistency_review.md`",
    ]
    (OUT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_consistency_review(summary: dict) -> None:
    lines = [
        "# Consistency Review",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- RFQ Gold Dataset scenarios: {summary['datasets']['rfq_gold_dataset']['record_count']}",
        f"- Supplier Intelligence records: {summary['datasets']['supplier_intelligence']['record_count']}",
        f"- Pricing Intelligence lines: {summary['datasets']['pricing_intelligence']['record_count']}",
        f"- Tender-Win Intelligence records: {summary['datasets']['tender_win_intelligence']['record_count']}",
        "",
        "## Validation Results",
        f"- JSON index validated: {summary['validation']['json_index']['ok']}",
        f"- YAML index validated: {summary['validation']['yaml_index']['ok']}",
        f"- Placeholder scan passed: {summary['validation']['placeholder_scan_passed']}",
        f"- Evidence-path check passed: {summary['validation']['source_path_check_passed']}",
        "",
        "## Metric Promotion Rule",
        "- Pack-local metrics are not automatically promoted to dashboard metrics.",
        "- Promotion requires a separate evidence review before any dashboard or maturity-summary update.",
        "",
        "## Readiness Read",
        "- RFQ Gold, Supplier Intelligence, and Pricing Intelligence now have a structured local pack with evidence paths and placeholder filtering.",
        "- Tender-Win Intelligence is materially enriched through governed outcome evidence, but award-confirmed taxonomy still needs a later normalization pass before treating it as external win intelligence.",
        "- The business-assets pack is prepared as a single documentation-side deliverable and stays outside execution-layer certification scope.",
        "",
        "## Open Notes",
        "- Supplier references remain source-derived strings in several records and still need future normalization into cleaner supplier master data.",
        "- Pricing intelligence records intentionally exclude placeholder lines but may still include low-confidence extracted line descriptions where the source artifact itself was low fidelity.",
    ]
    (OUT_DIR / "consistency_review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)

    rfq_gold = collect_rfq_gold()
    supplier_intelligence = collect_supplier_intelligence()
    pricing_intelligence = collect_pricing_intelligence()
    tender_win_intelligence = collect_tender_win_intelligence()

    rfq_path = DATASETS_DIR / "rfq_gold_dataset.jsonl"
    supplier_path = DATASETS_DIR / "supplier_intelligence.jsonl"
    pricing_path = DATASETS_DIR / "pricing_intelligence.jsonl"
    tender_path = DATASETS_DIR / "tender_win_intelligence.jsonl"

    write_jsonl(rfq_path, rfq_gold)
    write_jsonl(supplier_path, supplier_intelligence)
    write_jsonl(pricing_path, pricing_intelligence)
    write_jsonl(tender_path, tender_win_intelligence)

    validations = {
        "rfq_gold_dataset": validate_dataset("rfq_gold_dataset", rfq_gold),
        "supplier_intelligence": validate_dataset("supplier_intelligence", supplier_intelligence),
        "pricing_intelligence": validate_dataset("pricing_intelligence", pricing_intelligence),
        "tender_win_intelligence": validate_dataset("tender_win_intelligence", tender_win_intelligence),
    }

    summary = {
        "generated_at": utc_now(),
        "pack_name": "Business Intelligence Expansion Pack v1",
        "governance_position": {
            "status": "Controlled Production Candidate",
            "execution_layer": "Frozen",
            "governance": "Active",
            "regression_process": "Active",
            "next_formal_event": "Weekly Regression Run #2 pending valid trigger",
        },
        "datasets": {
            "rfq_gold_dataset": {
                "path": rel(rfq_path),
                "format": "jsonl",
                "record_count": len(rfq_gold),
                "source_count": validations["rfq_gold_dataset"]["source_count"],
            },
            "supplier_intelligence": {
                "path": rel(supplier_path),
                "format": "jsonl",
                "record_count": len(supplier_intelligence),
                "source_count": validations["supplier_intelligence"]["source_count"],
            },
            "pricing_intelligence": {
                "path": rel(pricing_path),
                "format": "jsonl",
                "record_count": len(pricing_intelligence),
                "source_count": validations["pricing_intelligence"]["source_count"],
            },
            "tender_win_intelligence": {
                "path": rel(tender_path),
                "format": "jsonl",
                "record_count": len(tender_win_intelligence),
                "source_count": validations["tender_win_intelligence"]["source_count"],
                "record_definition": "governed submission and outcome intelligence records",
            },
        },
        "validation": {
            "placeholder_scan_passed": all(result["placeholder_records"] == 0 for result in validations.values()),
            "source_path_check_passed": all(not result["missing_source_paths"] for result in validations.values()),
        },
        "notes": [
            "All records are sourced from local repo artifacts only.",
            "Placeholder pricing lines are excluded from the generated datasets.",
            "Tender-win records are not promoted here as external award confirmations.",
            "Pack-local metrics are not automatically promoted to dashboard metrics.",
            "Promotion requires a separate evidence review before any dashboard or maturity-summary update.",
        ],
    }

    index_json_path = OUT_DIR / "index.json"
    index_yaml_path = OUT_DIR / "index.yaml"
    write_json(index_json_path, summary)
    write_yaml(index_yaml_path, summary)

    summary["validation"]["json_index"] = validate_json(index_json_path)
    summary["validation"]["yaml_index"] = validate_yaml(index_yaml_path)

    write_json(index_json_path, summary)
    write_yaml(index_yaml_path, summary)
    write_readme(summary)
    write_consistency_review(summary)

    validation_summary = {
        "generated_at": summary["generated_at"],
        "dataset_validation": validations,
        "index_validation": summary["validation"],
    }
    write_json(OUT_DIR / "validation_summary.json", validation_summary)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
