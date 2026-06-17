from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


RUNTIME_DIR = Path("runtime")
LIVE_RFQ_FILE = RUNTIME_DIR / "live_rfqs.json"
SUBMISSION_HISTORY_FILE = RUNTIME_DIR / "submission_history" / "submission_history.json"
AWARD_DATA_FILE = Path("docs/business_assets_v2/datasets/tender_win_intelligence.jsonl")
SUBMISSION_PACKAGES_DIR = RUNTIME_DIR / "manual_production" / "submission_packages"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        text = str(value).strip().replace(",", "")
        for token in ("ZAR", "zar", "R", "$"):
            text = text.replace(token, "")
        return float(text.strip())
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    items: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _within_window(value: Any, window_start: datetime) -> bool:
    parsed = _parse_datetime(value)
    return bool(parsed and parsed >= window_start)


def _load_live_rfqs() -> List[Dict[str, Any]]:
    payload = _read_json(LIVE_RFQ_FILE, {})
    items = payload.get("items") if isinstance(payload, dict) else []
    return [item for item in _safe_list(items) if isinstance(item, dict)]


def _load_submission_history() -> List[Dict[str, Any]]:
    items = _read_json(SUBMISSION_HISTORY_FILE, [])
    return [item for item in _safe_list(items) if isinstance(item, dict)]


def _load_awards() -> List[Dict[str, Any]]:
    return _read_jsonl(AWARD_DATA_FILE)


def _load_supplier_response_files() -> List[Path]:
    if not SUBMISSION_PACKAGES_DIR.exists():
        return []
    files: List[Path] = []
    for package_dir in SUBMISSION_PACKAGES_DIR.iterdir():
        source_quotes = package_dir / "source_quotes"
        if not source_quotes.exists():
            continue
        for path in source_quotes.rglob("*"):
            if path.is_file():
                files.append(path)
    return files


def _count_live_funnel_items(items: Iterable[Dict[str, Any]], window_start: datetime) -> Dict[str, Any]:
    harvested = 0
    eligible = 0
    rejected = 0
    quoted = 0
    approved = 0
    supply_delivery_shape = 0
    quantity_possible = 0
    total_profit = 0.0
    total_margin = 0.0
    margin_count = 0
    total_value = 0.0

    for item in items:
        stamp = item.get("updated_at") or item.get("created_at") or item.get("published_at") or item.get("closing_at")
        if stamp and not _within_window(stamp, window_start):
            continue

        harvested += 1
        if bool(item.get("eligible")):
            eligible += 1
        if str(item.get("status") or "").strip().lower() in {"rejected", "blocked", "refused", "failed", "excluded"} or bool(item.get("screened_out")):
            rejected += 1
        if bool(item.get("quote_ready")) or bool(item.get("quote_generated")) or "quote_ready" in str(item.get("pipeline_status") or "").lower():
            quoted += 1
        if bool(item.get("auto_submission_gate_allowed")) or bool(item.get("submission_ready")) or "approved" in str(item.get("status") or "").lower():
            approved += 1
        if "supply" in str(item.get("category") or item.get("title") or item.get("description") or "").lower() or "delivery" in str(item.get("category") or item.get("title") or item.get("description") or "").lower():
            supply_delivery_shape += 1
        if bool(item.get("line_items")) or bool(item.get("boq_candidate_paths")) or bool(item.get("pricing_schedule_paths")) or bool(item.get("quote_ready")):
            quantity_possible += 1

        total_profit += _safe_float(item.get("estimated_profit"), 0.0)
        total_margin += _safe_float(item.get("gross_margin_ratio"), 0.0) or _safe_float(item.get("estimated_margin_pct"), 0.0) or _safe_float(item.get("margin_percent"), 0.0)
        if any(value is not None for value in [item.get("gross_margin_ratio"), item.get("estimated_margin_pct"), item.get("margin_percent")]):
            margin_count += 1
        total_value += _safe_float(item.get("estimated_contract_value"), 0.0)

    return {
        "rfqs_harvested": harvested,
        "rfqs_eligible": eligible,
        "rfqs_rejected": rejected,
        "rfqs_quoted": quoted,
        "rfqs_approved": approved,
        "supply_delivery_shape": supply_delivery_shape,
        "quantity_verification_possible": quantity_possible,
        "estimated_contract_value": round(total_value, 2),
        "expected_gross_profit": round(total_profit, 2),
        "average_margin": round((total_margin / margin_count) if margin_count else 0.0, 4),
    }


def _count_submission_metrics(items: Iterable[Dict[str, Any]], window_start: datetime) -> Dict[str, Any]:
    submissions = 0
    proofs = 0
    submitted_value = 0.0
    actual_profit = 0.0
    by_status: Dict[str, int] = defaultdict(int)

    for item in items:
        stamp = item.get("receipt_timestamp") or item.get("created_at") or item.get("updated_at")
        if stamp and not _within_window(stamp, window_start):
            continue

        status = str(item.get("status") or "").strip().lower() or "unknown"
        by_status[status] += 1
        if status == "submitted":
            submissions += 1
        if item.get("proof_path") or item.get("proof_generated") or item.get("proof_pdf_path") or item.get("receipt_text"):
            proofs += 1

        submitted_value += _safe_float(
            item.get("estimated_revenue")
            or _safe_dict(item.get("metadata")).get("estimated_revenue")
            or _safe_dict(item.get("raw_result")).get("estimated_revenue"),
            0.0,
        )
        actual_profit += _safe_float(
            item.get("actual_gross_profit")
            or item.get("realized_profit")
            or _safe_dict(item.get("metadata")).get("actual_gross_profit")
            or _safe_dict(item.get("raw_result")).get("actual_gross_profit")
            or _safe_dict(item.get("metadata")).get("estimated_profit")
            or _safe_dict(item.get("raw_result")).get("estimated_profit"),
            0.0,
        )

    return {
        "quotes_submitted": submissions,
        "submission_records": submissions,
        "proof_records": proofs,
        "submitted_value": round(submitted_value, 2),
        "actual_gross_profit": round(actual_profit, 2),
        "submission_status_counts": dict(sorted(by_status.items())),
    }


def _count_award_metrics(items: Iterable[Dict[str, Any]], window_start: datetime) -> Dict[str, Any]:
    awards = 0
    award_value = 0.0
    unique_awardees: set[str] = set()
    province_awardees: Dict[str, set[str]] = defaultdict(set)
    category_awards: Dict[str, int] = defaultdict(int)

    for item in items:
        if not _within_window(item.get("event_at"), window_start):
            continue
        if str(item.get("verification_status") or "").strip().lower() not in {"award confirmed", "confirmed", "awarded"}:
            continue

        awards += 1
        award_value += _safe_float(item.get("price"), 0.0)
        awardee = str(item.get("awardee") or "").strip() or "unknown"
        province = str(item.get("province") or "").strip() or "unknown"
        category = str(item.get("category") or "").strip() or "unknown"
        unique_awardees.add(awardee)
        province_awardees[province].add(awardee)
        category_awards[category] += 1

    return {
        "awards_won": awards,
        "awards_lost": 0,
        "awarded_value": round(award_value, 2),
        "unique_awardees": len(unique_awardees),
        "awardees_by_province": {province: len(values) for province, values in sorted(province_awardees.items())},
        "awards_by_category": dict(sorted(category_awards.items(), key=lambda item: (-item[1], item[0]))),
    }


def _count_supplier_metrics(items: Iterable[Dict[str, Any]], window_start: datetime) -> Dict[str, Any]:
    requests_sent = 0
    lead_times: List[float] = []
    coverage_by_province: Dict[str, set[str]] = defaultdict(set)

    for item in items:
        stamp = item.get("updated_at") or item.get("created_at") or item.get("published_at")
        if stamp and not _within_window(stamp, window_start):
            continue

        if bool(item.get("quote_ready")) or bool(item.get("quote_generated")) or bool(item.get("submission_ready")):
            requests_sent += 1
            published = _parse_datetime(item.get("published_at"))
            closing = _parse_datetime(item.get("closing_at") or item.get("closing_date"))
            if published and closing and closing > published:
                lead_times.append((closing - published).total_seconds() / 3600.0)

    response_files = [path for path in _load_supplier_response_files() if _within_window(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc), window_start)]
    supplier_responses_received = len(response_files)
    for award in _load_awards():
        if not _within_window(award.get("event_at"), window_start):
            continue
        province = str(award.get("province") or "").strip() or "unknown"
        awardee = str(award.get("awardee") or "").strip() or "unknown"
        coverage_by_province[province].add(awardee)

    return {
        "supplier_requests_sent": requests_sent,
        "supplier_responses_received": supplier_responses_received,
        "supplier_response_rate": round((supplier_responses_received / requests_sent) if requests_sent else 0.0, 4),
        "average_supplier_lead_time_hours": round(sum(lead_times) / len(lead_times), 2) if lead_times else 0.0,
        "supplier_coverage_by_province": {province: len(values) for province, values in sorted(coverage_by_province.items())},
    }


def build_weekly_operations_report(window_days: int = 7, limit: int = 25) -> Dict[str, Any]:
    window_days = max(1, min(_safe_int(window_days, 7), 365))
    limit = max(1, min(_safe_int(limit, 25), 1000))
    window_end = _utc_now()
    window_start = window_end - timedelta(days=window_days)

    live_rfqs = _load_live_rfqs()
    submission_history = _load_submission_history()
    awards = _load_awards()

    procurement_funnel = _count_live_funnel_items(live_rfqs, window_start)
    submission_metrics = _count_submission_metrics(submission_history, window_start)
    award_metrics = _count_award_metrics(awards, window_start)
    supplier_metrics = _count_supplier_metrics(live_rfqs, window_start)

    quotes_submitted = submission_metrics["quotes_submitted"]
    awards_won = award_metrics["awards_won"]
    award_metrics["awards_lost"] = max(0, quotes_submitted - awards_won)
    win_rate = round((awards_won / quotes_submitted) if quotes_submitted else 0.0, 4)
    profit_per_rfq = round((procurement_funnel["expected_gross_profit"] / procurement_funnel["rfqs_quoted"]) if procurement_funnel["rfqs_quoted"] else 0.0, 2)

    report = {
        "status": "ok",
        "generated_at": _utc_now_iso(),
        "window_days": window_days,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "data_source": "runtime/live_rfqs + runtime/submission_history + docs/business_assets_v2/datasets/tender_win_intelligence.jsonl",
        "procurement_funnel": procurement_funnel | {
            "rfqs_processed": procurement_funnel["rfqs_harvested"],
            "rfqs_qualified": procurement_funnel["rfqs_eligible"],
            "rfqs_rejected": procurement_funnel["rfqs_rejected"],
            "rfqs_quoted": procurement_funnel["rfqs_quoted"],
            "rfqs_approved": procurement_funnel["rfqs_approved"],
            "rfqs_submitted": quotes_submitted,
            "awards_won": awards_won,
            "awards_lost": award_metrics["awards_lost"],
            "win_rate": win_rate,
        },
        "financial_funnel": {
            "estimated_award_value": award_metrics["awarded_value"],
            "submitted_value": submission_metrics["submitted_value"],
            "awarded_value": award_metrics["awarded_value"],
            "expected_gross_profit": procurement_funnel["expected_gross_profit"],
            "actual_gross_profit": submission_metrics["actual_gross_profit"],
            "average_margin": procurement_funnel["average_margin"],
            "profit_per_rfq": profit_per_rfq,
        },
        "supplier_funnel": supplier_metrics,
        "award_intelligence": award_metrics,
        "submission_metrics": submission_metrics,
        "summary": {
            "rfqs_harvested": procurement_funnel["rfqs_harvested"],
            "rfqs_eligible": procurement_funnel["rfqs_eligible"],
            "rfqs_rejected": procurement_funnel["rfqs_rejected"],
            "rfqs_quoted": procurement_funnel["rfqs_quoted"],
            "rfqs_approved": procurement_funnel["rfqs_approved"],
            "rfqs_submitted": quotes_submitted,
            "awards_won": awards_won,
            "win_rate": win_rate,
            "award_value": award_metrics["awarded_value"],
            "expected_gross_profit": procurement_funnel["expected_gross_profit"],
            "actual_gross_profit": submission_metrics["actual_gross_profit"],
            "supplier_response_rate": supplier_metrics["supplier_response_rate"],
        },
        "notes": [
            "Procurement counts are derived from the current runtime live RFQ store.",
            "Submission counts are derived from the submission history log.",
            "Award counts are derived from award-confirmed public award notices.",
            "Supplier response counts are derived from copied source-quote artifacts when available.",
            "Actual gross profit is only populated where submission history carries profit evidence.",
        ],
    }

    return report


def build_weekly_operations_summary(limit: int = 25) -> Dict[str, Any]:
    report = build_weekly_operations_report(limit=limit)
    return {
        "status": report["status"],
        "generated_at": report["generated_at"],
        "summary": report["summary"],
        "procurement_funnel": report["procurement_funnel"],
        "financial_funnel": report["financial_funnel"],
        "supplier_funnel": report["supplier_funnel"],
        "award_intelligence": report["award_intelligence"],
        "data_source": report["data_source"],
        "notes": report["notes"],
    }
