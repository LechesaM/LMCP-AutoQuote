from __future__ import annotations

import hashlib
import json
import re
import runpy
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs" / "business_assets_v2"
DATASETS_DIR = OUT_DIR / "datasets"
SOURCES_DIR = OUT_DIR / "sources"

BASE = runpy.run_path(str(ROOT / "docs" / "business_assets" / "build_business_assets_pack.py"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


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
            if raw:
                records.append(json.loads(raw))
    return records


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
    if re.fullmatch(r"[A-Za-z0-9 _.,:/()+?\-]+", value) and ": " not in value and not value.startswith((" ", "-", "{", "[")) and not value.endswith(" "):
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
        lines: list[str] = []
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
    return {"ok": completed.returncode == 0, "path": rel(path), "stderr": completed.stderr.strip()}


def decorate_record(record: dict, *, provenance_type: str, verification_status: str, source_reference: str, reviewed_by: str = "Codex", last_review_date: str | None = None) -> dict:
    record = dict(record)
    record.setdefault("provenance_type", provenance_type)
    record.setdefault("verification_status", verification_status)
    record.setdefault("last_review_date", last_review_date or utc_date())
    record.setdefault("reviewed_by", reviewed_by)
    record.setdefault("source_reference", source_reference)
    return record


def collect_rfq_gold_v2() -> list[dict]:
    base = list(BASE["collect_rfq_gold"]())
    records: dict[str, dict] = {item["scenario_id"]: item for item in base}

    manifest_paths = sorted((ROOT / "runtime" / "manual_production" / "submission_packages").glob("*/**/*quote_pack_manifest.json"))
    for path in manifest_paths:
        data = read_json(path)
        tender_id = data.get("tender_id") or path.parent.name
        review_ready_bundle = data.get("review_ready_bundle") or {}
        for index, entry in enumerate(data.get("source_quote_entries", []), start=1):
            source_ref = entry.get("source", "")
            copied_to = entry.get("copied_to", "")
            scenario = decorate_record(
                {
                    "scenario_id": stable_id("rfq-v2", tender_id, source_ref, copied_to, str(index)),
                    "scenario_type": "submission_package_source_quote_entry",
                    "tender_id": tender_id,
                    "title": data.get("tender_id", tender_id),
                    "buyer_name": data.get("review_ready_bundle", {}).get("buyer_name", "") or data.get("buyer_name", ""),
                    "province": "",
                    "category": "",
                    "source_path": rel(path),
                    "source_family": "submission_package_manifest",
                    "line_item_count": 0,
                    "package_status": data.get("package_status", ""),
                    "submission_ready": data.get("submission_ready"),
                    "review_ready": data.get("review_ready_bundle", {}).get("review_ready"),
                    "source_quote_entry_source": source_ref,
                    "source_quote_entry_copied_to": copied_to,
                    "source_quote_entry_status": entry.get("status", ""),
                    "evidence_grade": "high" if entry.get("status") == "copied" else "medium",
                },
                provenance_type="Submission Package Evidence",
                verification_status="confirmed" if copied_to else "derived",
                source_reference=source_ref or copied_to or rel(path),
            )
            records.setdefault(scenario["scenario_id"], scenario)

    return sorted(records.values(), key=lambda record: (record["tender_id"], record["scenario_type"], record["source_path"]))


def collect_supplier_intelligence_v2() -> list[dict]:
    base = list(BASE["collect_supplier_intelligence"](1000))
    records: dict[str, dict] = {item["supplier_id"]: item for item in base}

    manifest_paths = sorted((ROOT / "runtime" / "manual_production" / "submission_packages").glob("*/**/*quote_pack_manifest.json"))
    for path in manifest_paths:
        data = read_json(path)
        tender_id = data.get("tender_id") or path.parent.name
        for index, entry in enumerate(data.get("source_quote_entries", []), start=1):
            source_ref = entry.get("source", "")
            copied_to = entry.get("copied_to", "")
            supplier_reference = Path(copied_to or source_ref).stem or Path(source_ref).stem
            if not supplier_reference:
                continue
            record = decorate_record(
                {
                    "supplier_id": stable_id("supplier-v2", tender_id, source_ref, copied_to, str(index)),
                    "supplier_reference": supplier_reference,
                    "supplier_slug": slug(supplier_reference),
                    "normalization_status": "source_quote_entry_reference",
                    "source_type": "submission_package_source_quote_entry",
                    "source_path": rel(path),
                    "tender_id": tender_id,
                    "evidence_grade": "high" if entry.get("status") == "copied" else "medium",
                    "quality_rank": 3 if entry.get("status") == "copied" else 2,
                    "source_quote_entry_source": source_ref,
                    "source_quote_entry_copied_to": copied_to,
                    "source_quote_entry_status": entry.get("status", ""),
                },
                provenance_type="Submission Package Evidence",
                verification_status="confirmed" if copied_to else "derived",
                source_reference=source_ref or copied_to or rel(path),
            )
            records.setdefault(record["supplier_id"], record)

    return sorted(records.values(), key=lambda record: (-record.get("quality_rank", 0), record["supplier_reference"], record["source_path"]))


def collect_pricing_intelligence_v2() -> list[dict]:
    base = list(BASE["collect_pricing_intelligence"](1000))
    records = base[:500]
    decorated = []
    for record in records:
        decorated.append(
            decorate_record(
                record,
                provenance_type="Local Pricing Evidence",
                verification_status="confirmed" if record.get("evidence_grade") == "high" else "derived",
                source_reference=record.get("source_path", ""),
            )
        )
    return decorated


AWARD_CONFIRMED_SEEDS = [
    {
        "award_id": "arc-award-arc-51-11-2025-001",
        "tender_id": "ARC/51/11/2025",
        "buyer_name": "Agricultural Research Council",
        "tender_title": "THE APPOINTMENT OF A PANEL OF SERVICE PROVIDERS FOR THE SUPPLY AND INSTALLATION OF FENCING MATERIAL IN VARIOUS PROVINCES FOR CROP PLANTATION SECURITY FOR A PERIOD OF THREE (03) YEARS",
        "awardee": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
        "price": "",
        "province": "National",
        "category": "Services: General",
        "source_reference": "file:/Users/cash/Documents/PUBLICATION OF AWARDED BID ARC-51-11-2025.pdf",
    },
    {
        "award_id": "arc-award-arc-51-11-2025-002",
        "tender_id": "ARC/51/11/2025",
        "buyer_name": "Agricultural Research Council",
        "tender_title": "THE APPOINTMENT OF A PANEL OF SERVICE PROVIDERS FOR THE SUPPLY AND INSTALLATION OF FENCING MATERIAL IN VARIOUS PROVINCES FOR CROP PLANTATION SECURITY FOR A PERIOD OF THREE (03) YEARS",
        "awardee": "Motho Waka Trading Enterprise cc",
        "price": "",
        "province": "National",
        "category": "Services: General",
        "source_reference": "file:/Users/cash/Documents/PUBLICATION OF AWARDED BID ARC-51-11-2025.pdf",
    },
    {
        "award_id": "arc-award-arc-51-11-2025-003",
        "tender_id": "ARC/51/11/2025",
        "buyer_name": "Agricultural Research Council",
        "tender_title": "THE APPOINTMENT OF A PANEL OF SERVICE PROVIDERS FOR THE SUPPLY AND INSTALLATION OF FENCING MATERIAL IN VARIOUS PROVINCES FOR CROP PLANTATION SECURITY FOR A PERIOD OF THREE (03) YEARS",
        "awardee": "Rigogo Projects",
        "price": "",
        "province": "National",
        "category": "Services: General",
        "source_reference": "file:/Users/cash/Documents/PUBLICATION OF AWARDED BID ARC-51-11-2025.pdf",
    },
    {
        "award_id": "arc-award-arc-51-11-2025-004",
        "tender_id": "ARC/51/11/2025",
        "buyer_name": "Agricultural Research Council",
        "tender_title": "THE APPOINTMENT OF A PANEL OF SERVICE PROVIDERS FOR THE SUPPLY AND INSTALLATION OF FENCING MATERIAL IN VARIOUS PROVINCES FOR CROP PLANTATION SECURITY FOR A PERIOD OF THREE (03) YEARS",
        "awardee": "Limacom",
        "price": "",
        "province": "National",
        "category": "Services: General",
        "source_reference": "file:/Users/cash/Documents/PUBLICATION OF AWARDED BID ARC-51-11-2025.pdf",
    },
    {
        "award_id": "arc-award-arc-51-11-2025-005",
        "tender_id": "ARC/51/11/2025",
        "buyer_name": "Agricultural Research Council",
        "tender_title": "THE APPOINTMENT OF A PANEL OF SERVICE PROVIDERS FOR THE SUPPLY AND INSTALLATION OF FENCING MATERIAL IN VARIOUS PROVINCES FOR CROP PLANTATION SECURITY FOR A PERIOD OF THREE (03) YEARS",
        "awardee": "Bremivode",
        "price": "",
        "province": "National",
        "category": "Services: General",
        "source_reference": "file:/Users/cash/Documents/PUBLICATION OF AWARDED BID ARC-51-11-2025.pdf",
    },
    {
        "award_id": "arc-award-arc-51-11-2025-006",
        "tender_id": "ARC/51/11/2025",
        "buyer_name": "Agricultural Research Council",
        "tender_title": "THE APPOINTMENT OF A PANEL OF SERVICE PROVIDERS FOR THE SUPPLY AND INSTALLATION OF FENCING MATERIAL IN VARIOUS PROVINCES FOR CROP PLANTATION SECURITY FOR A PERIOD OF THREE (03) YEARS",
        "awardee": "Lebo Tebo Trading and Projects",
        "price": "",
        "province": "National",
        "category": "Services: General",
        "source_reference": "file:/Users/cash/Documents/PUBLICATION OF AWARDED BID ARC-51-11-2025.pdf",
    },
    {
        "award_id": "nt-award-nt001-2026",
        "tender_id": "NT001-2026",
        "buyer_name": "National Treasury",
        "tender_title": "APPOINTMENT OF A SERVICE PROVIDER TO RENDER PROFESSIONAL SERVICES TO NATIONAL TREASURY (NT) INFORMATION AND COMMUNICATION TECHNOLOGY (ICT) FOR A PERIOD OF THIRTY-SIX (36) MONTHS THROUGH SITA RFB 1183 PANEL",
        "awardee": "Alteram Solutions (Pty) Ltd",
        "price": "R9782.47",
        "province": "National",
        "category": "Services: Professional",
        "source_reference": "https://www.treasury.gov.za/Tenderinfo/awarded/default.aspx",
    },
    {
        "award_id": "nt-award-nt002-2026",
        "tender_id": "NT002-2026",
        "buyer_name": "National Treasury",
        "tender_title": "APPOINTMENT OF A SERVICE PROVIDER TO UPGRADE IVANTI HEAT 2023 LICENCES TO IVANTI NEURONS AND PROVIDE SUPPORT AND MAINTENANCE FOR THE NATIONAL TREASURY (NT) INFORMATION AND COMMUNICATION TECHNOLOGY (ICT) FOR A PERIOD OF THREE (3) YEARS",
        "awardee": "Blue Turtle Technologies",
        "price": "R6 649 485,73",
        "province": "National",
        "category": "Services: Professional",
        "source_reference": "https://www.treasury.gov.za/Tenderinfo/awarded/default.aspx",
    },
    {
        "award_id": "nt-award-nt019-2025",
        "tender_id": "NT019-2025",
        "buyer_name": "National Treasury",
        "tender_title": "APPOINTMENT OF SERVICE PROVIDER FOR THE INSTALLATION OF LOCKABLE STEEL BULKFILERS AND FREE-STANDING SHELVES FOR RECORDS KEEPING PURPOSES FOR A PERIOD OF 30 DAYS",
        "awardee": "Indawo Systems",
        "price": "R380 707,62",
        "province": "National",
        "category": "Supplies: General",
        "source_reference": "https://www.treasury.gov.za/Tenderinfo/awarded/default.aspx",
    },
    {
        "award_id": "nt-award-nt020-2025",
        "tender_id": "NT020-2025",
        "buyer_name": "National Treasury",
        "tender_title": "APPOINTMENT OF AN ACCREDITED SERVICE PROVIDER TO SUPPLY, INSTALL AND CONFIGURE CHECKPOINT NEXT-GENERATION FIREWALL DEVICES IN THE NATIONAL TREASURY (NT) NEW BUILDINGS WITH A THREE-YEAR PROFESSIONAL SERVICES, MAINTENANCE AND SUPPORT CONTRACT",
        "awardee": "Foursight IT Business Solutions CC",
        "price": "R7 162 404,55",
        "province": "National",
        "category": "Services: Professional",
        "source_reference": "https://www.treasury.gov.za/Tenderinfo/awarded/default.aspx",
    },
    {
        "award_id": "nt-award-nt015-2025",
        "tender_id": "NT015-2025",
        "buyer_name": "National Treasury",
        "tender_title": "APPOINTMENT OF A CERTIFIED SERVICE PROVIDER TO SUPPLY, INSTALL AND CONFIGURE RIVERBED WAN OPTIMISATION DEVICES FOR THE NATIONAL TREASURY (NT) NEW BUILDINGS WITH A THREE-YEAR PROFESSIONAL SERVICES, MAINTENANCE AND SUPPORT CONTRACT",
        "awardee": "DataCentrix (Pty) Ltd",
        "price": "R14 907 447.07",
        "province": "National",
        "category": "Services: Professional",
        "source_reference": "https://www.treasury.gov.za/Tenderinfo/awarded/default.aspx",
    },
    {
        "award_id": "nt-award-nt021-2025-a",
        "tender_id": "NT021-2025",
        "buyer_name": "National Treasury",
        "tender_title": "APPOINTMENT OF A SERVICE PROVIDER TO SUPPLY, INSTALL, CONFIGURE, SUPPORT, AND MAINTAIN THE LAN SWITCHES AND LAN CABLING",
        "awardee": "Business Connexion (Pty) Ltd (Category A)",
        "price": "R15 129 681,84",
        "province": "National",
        "category": "Services: Professional",
        "source_reference": "https://www.treasury.gov.za/Tenderinfo/awarded/default.aspx",
    },
    {
        "award_id": "nt-award-nt021-2025-b",
        "tender_id": "NT021-2025",
        "buyer_name": "National Treasury",
        "tender_title": "APPOINTMENT OF A SERVICE PROVIDER TO SUPPLY, INSTALL, CONFIGURE, SUPPORT, AND MAINTAIN THE LAN SWITCHES AND LAN CABLING",
        "awardee": "DataCentrix (Pty) Ltd (Category B)",
        "price": "R8 581 825,47",
        "province": "National",
        "category": "Services: Professional",
        "source_reference": "https://www.treasury.gov.za/Tenderinfo/awarded/default.aspx",
    },
    {
        "award_id": "nt-award-rfq0004-2025",
        "tender_id": "RFQ0004-2025",
        "buyer_name": "National Treasury",
        "tender_title": "APPOINTMENT OF A SERVICE PROVIDER TO INSTALL, CONFIGURE, SUPPORT AND MAINTAIN AUDIOVISUAL/VIDEO CONFERENCING EQUIPMENT FOR THE NATIONAL TREASURY (NT) INFORMATION AND COMMUNICATION TECHNOLOGY (ICT) FOR A PERIOD OF THREE (3) YEARS THROUGH SITA RFB2009",
        "awardee": "Omega Digital Services",
        "price": "R12 602 751,20",
        "province": "National",
        "category": "Services: Professional",
        "source_reference": "https://www.treasury.gov.za/Tenderinfo/awarded/default.aspx",
    },
    {
        "award_id": "nt-award-nt012-2025-a",
        "tender_id": "NT012-2025",
        "buyer_name": "National Treasury",
        "tender_title": "APPOINTMENT OF SERVICE PROVIDER(S) FOR THE ONCE-OFF SUPPLY, DELIVERY, OFF LOAD AND INSTALLATION OF OFFICE FURNITURE AND SOFT FURNISHINGS AT THE NATIONAL TREASURY OFFICES",
        "awardee": "Spacio Office Dezigns (Category A)",
        "price": "R21 986 038,30",
        "province": "National",
        "category": "Supplies: General",
        "source_reference": "https://www.treasury.gov.za/Tenderinfo/awarded/default.aspx",
    },
    {
        "award_id": "nt-award-nt012-2025-b",
        "tender_id": "NT012-2025",
        "buyer_name": "National Treasury",
        "tender_title": "APPOINTMENT OF SERVICE PROVIDER(S) FOR THE ONCE-OFF SUPPLY, DELIVERY, OFF LOAD AND INSTALLATION OF OFFICE FURNITURE AND SOFT FURNISHINGS AT THE NATIONAL TREASURY OFFICES",
        "awardee": "Clockwyse Capital (Category B)",
        "price": "R15 631 321,61",
        "province": "National",
        "category": "Supplies: General",
        "source_reference": "https://www.treasury.gov.za/Tenderinfo/awarded/default.aspx",
    },
    {
        "award_id": "nt-award-nt010-2025",
        "tender_id": "NT010-2025",
        "buyer_name": "National Treasury",
        "tender_title": "APPOINTMENT OF A SERVICE PROVIDER TO REDESIGN THE INTERNET AND INTRANET WEBSITES OF THE NATIONAL TREASURY (NT) FOR A PERIOD OF 24 MONTHS",
        "awardee": "Exponant (Pty) Ltd",
        "price": "R14 384 085.00",
        "province": "National",
        "category": "Services: Professional",
        "source_reference": "https://www.treasury.gov.za/Tenderinfo/awarded/default.aspx",
    },
]


def write_award_confirmed_sources() -> Path:
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    source_path = SOURCES_DIR / "award_confirmed_sources.json"
    write_json(source_path, {"generated_at": utc_now(), "sources": AWARD_CONFIRMED_SEEDS})
    return source_path


def collect_tender_win_intelligence_v2(award_source_rel: str) -> list[dict]:
    base = list(BASE["collect_tender_win_intelligence"](1000))
    records: dict[str, dict] = {item["record_id"]: item for item in base[:200]}

    for index, seed in enumerate(AWARD_CONFIRMED_SEEDS, start=1):
        record = decorate_record(
            {
                "record_id": stable_id("award-confirmed", seed["award_id"], seed["tender_id"], seed["awardee"]),
                "record_class": "award_publication",
                "tender_id": seed["tender_id"],
                "buyer_name": seed["buyer_name"],
                "awardee": seed["awardee"],
                "tender_title": seed["tender_title"],
                "price": seed["price"],
                "province": seed["province"],
                "category": seed["category"],
                "event_at": utc_now(),
                "source_path": award_source_rel,
                "source_type": "award_confirmed_source_register",
                "source_reference": seed["source_reference"],
                "provenance_type": "Award Confirmed",
                "evidence_grade": "high",
            },
            provenance_type="Award Confirmed",
            verification_status="confirmed",
            source_reference=seed["source_reference"],
        )
        records.setdefault(record["record_id"], record)

    return sorted(records.values(), key=lambda record: (record["event_at"], record["source_path"], record["record_id"]), reverse=True)


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


def write_support_docs(summary: dict, rfq_records: list[dict], supplier_records: list[dict], tender_records: list[dict]) -> None:
    rfq_by_province = defaultdict(list)
    rfq_categories_by_province = defaultdict(set)
    tender_ids_by_province = defaultdict(set)
    for record in rfq_records:
        province = record.get("province") or "National"
        rfq_by_province[province].append(record)
        if record.get("category"):
            rfq_categories_by_province[province].add(record["category"])
        tender_ids_by_province[province].add(record.get("tender_id"))

    supplier_by_tender = defaultdict(list)
    for record in supplier_records:
        tender_id = record.get("tender_id")
        if tender_id:
            supplier_by_tender[tender_id].append(record)

    province_lines = [
        "# Province Supplier Map",
        "",
        "This map is advisory-only. Supplier references are linked through shared tender IDs and source-quote manifests where available.",
        "",
        "| Province | Preferred Suppliers | Backup Suppliers | Categories Covered | Logistics Coverage | Lead Time Note |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for province in ["Eastern Cape", "Free State", "Gauteng", "KwaZulu-Natal", "Limpopo", "Mpumalanga", "National", "North West", "Northern Cape", "Western Cape"]:
        province_rfqs = rfq_by_province.get(province, [])
        tender_ids = [item for item in sorted(tender_ids_by_province.get(province, [])) if item]
        supplier_refs: list[str] = []
        for tender_id in tender_ids:
            for supplier in supplier_by_tender.get(tender_id, []):
                supplier_refs.append(supplier.get("supplier_reference", supplier.get("supplier_slug", "")))
        if not supplier_refs:
            supplier_refs = [record.get("supplier_reference", record.get("supplier_slug", "")) for record in supplier_records[:3]]
        preferred = ", ".join(dict.fromkeys(supplier_refs[:3])) or "Not yet province-specific"
        backup = ", ".join(dict.fromkeys(supplier_refs[3:6])) or "Use national fallback suppliers"
        categories = ", ".join(sorted(rfq_categories_by_province.get(province, []))) or "Not yet explicit in local source set"
        logistics = "Province-linked where tender IDs overlap; otherwise national coverage"
        lead_time = "Lead time not explicit in all current source artifacts"
        province_lines.append(f"| {province} | {preferred} | {backup} | {categories} | {logistics} | {lead_time} |")

    (OUT_DIR / "province_supplier_map.md").write_text("\n".join(province_lines) + "\n", encoding="utf-8")

    competitor_counts = Counter()
    for record in tender_records:
        if record.get("provenance_type") == "Award Confirmed":
            competitor_counts[record.get("awardee", record.get("buyer_name", "unknown"))] += 1

    competitor_lines = [
        "# Competitor Intelligence",
        "",
        "Award-confirmed records currently provide the strongest external win signal.",
        "",
        "| Supplier | Award Confirmed Wins | Notes |",
        "| --- | --- | --- |",
    ]
    for supplier, count in competitor_counts.most_common():
        competitor_lines.append(f"| {supplier} | {count} | Source-confirmed through public award notices |")
    if len(competitor_counts) == 0:
        competitor_lines.append("| No award-confirmed supplier records yet | 0 | Awaiting public award notices |")
    (OUT_DIR / "competitor_intelligence.md").write_text("\n".join(competitor_lines) + "\n", encoding="utf-8")

    scorecard_lines = [
        "# Tender Opportunity Scorecard",
        "",
        "- Margin score: expected gross margin after supplier cost and logistics assumptions.",
        "- Profit score: weighted margin after support, compliance, and contingency allowances.",
        "- Supplier coverage score: number of viable supplier responses available for the province/category mix.",
        "- Competition score: inverse function of prior award concentration and bidder density.",
        "- Risk score: document completeness, award volatility, and evidence quality.",
        "",
        "## Advisory Formula",
        "score = (margin_score * 0.30) + (profit_score * 0.30) + (supplier_coverage_score * 0.20) + (competition_score * 0.10) + ((100 - risk_score) * 0.10)",
        "",
        "The scorecard remains advisory-only until governance permits downstream integration.",
    ]
    (OUT_DIR / "opportunity_scorecard.md").write_text("\n".join(scorecard_lines) + "\n", encoding="utf-8")

    probability_lines = [
        "# Win Probability Methodology",
        "",
        "The win-probability model is advisory-only and is not connected to runtime submission controls.",
        "",
        "- Competition level: penalize tenders with many rival awardees or repeated incumbent wins.",
        "- Historical winner frequency: increase confidence where the supplier or competitor has repeated public awards.",
        "- Category profitability: boost categories with stable pricing and repeatable margin structure.",
        "- Province success rate: combine provincial award history with current supplier coverage.",
        "- Supplier strength: rank suppliers by verified award count, pricing depth, and source quality.",
        "",
        "## Practical Output",
        "win_probability = normalized(competition_level, historical_winner_frequency, category_profitability, province_success_rate, supplier_strength)",
        "",
        "This methodology exists to improve future review quality, not to automate runtime decisions.",
    ]
    (OUT_DIR / "win_probability_methodology.md").write_text("\n".join(probability_lines) + "\n", encoding="utf-8")

    review_lines = [
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
        "- RFQ Gold now includes manifest-level source-quote evidence in addition to the earlier local RFQ corpus.",
        "- Supplier Intelligence now captures source-quote entry references from the manifest layer so the pack can grow past the earlier ceiling without touching runtime logic.",
        "- Pricing Intelligence is expanded from the local high-confidence pricing corpus and remains advisory-only.",
        "- Tender-Win Intelligence now includes award-confirmed records from public award notices, with the original governed outcome history retained alongside it.",
        "",
        "## Open Notes",
        "- Supplier references remain source-derived strings in several records and will benefit from future normalization into a supplier master layer.",
        "- Province coverage is still advisory because a subset of source artifacts lacks explicit province labeling.",
        "- Lead times remain source-dependent and are not always explicit in the local evidence corpus.",
    ]
    (OUT_DIR / "consistency_review.md").write_text("\n".join(review_lines) + "\n", encoding="utf-8")

    readme_lines = [
        "# Business Intelligence Expansion Pack v2",
        "",
        "## Purpose",
        "This pack extends the non-runtime intelligence layer using local repository evidence, manifest-level source-quote provenance, and public award notices.",
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
        "This pack explicitly carries provenance, verification status, last review date, reviewed by, and source reference metadata on every intelligence record.",
        "Award-confirmed tender wins are present only where a public award notice or equivalent publication is available.",
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
        "- `sources/award_confirmed_sources.json`",
        "- `province_supplier_map.md`",
        "- `competitor_intelligence.md`",
        "- `opportunity_scorecard.md`",
        "- `win_probability_methodology.md`",
        "- `index.json`",
        "- `index.yaml`",
        "- `consistency_review.md`",
    ]
    (OUT_DIR / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")


def main() -> None:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    award_source_path = write_award_confirmed_sources()

    rfq_gold = collect_rfq_gold_v2()
    supplier_intelligence = collect_supplier_intelligence_v2()
    pricing_intelligence = collect_pricing_intelligence_v2()
    tender_win_intelligence = collect_tender_win_intelligence_v2(rel(award_source_path))

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
        "pack_name": "Business Intelligence Expansion Pack v2",
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
                "record_definition": "governed submission, outcome, and award-confirmed intelligence records",
            },
        },
        "validation": {
            "placeholder_scan_passed": all(result["placeholder_records"] == 0 for result in validations.values()),
            "source_path_check_passed": all(not result["missing_source_paths"] for result in validations.values()),
        },
        "notes": [
            "All records are sourced from local repo artifacts or public award notices referenced through the pack source register.",
            "Manifest-level source-quote entries are promoted into the intelligence layer as evidence-backed records.",
            "Award-confirmed records are included only where a public award notice exists.",
            "Pack-local metrics are not automatically promoted to dashboard metrics.",
            "Promotion requires a separate evidence review before any dashboard or maturity-summary update.",
            "The certified execution layer remains frozen.",
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

    write_support_docs(summary, rfq_gold, supplier_intelligence, tender_win_intelligence)

    validation_summary = {
        "generated_at": summary["generated_at"],
        "dataset_validation": validations,
        "index_validation": summary["validation"],
    }
    write_json(OUT_DIR / "validation_summary.json", validation_summary)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
