from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


@dataclass
class SourceStats:
    source: str
    harvested_count: int = 0
    quote_ready_count: int = 0
    submitted_count: int = 0
    error_count: int = 0
    last_checked_at: Optional[str] = None
    last_success_at: Optional[str] = None
    last_deadline_seen_at: Optional[str] = None
    average_items_per_run: float = 0.0
    priority_score: float = 0.0
    crawl_interval_minutes: int = 60


def utcnow() -> datetime:
    return datetime.utcnow()


def parse_dt(value: Optional[str]) -> Optional[datetime]:
    """
    Parse ISO datetime safely.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def to_iso(value: Optional[datetime]) -> Optional[str]:
    """
    Convert datetime to ISO string safely.
    """
    if value is None:
        return None
    return value.isoformat()


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def compute_priority_score(stats: SourceStats) -> float:
    """
    Compute source priority based on productivity and reliability.
    Higher score = crawl more often.
    """
    harvested_weight = min(stats.harvested_count, 200) * 0.15
    quote_ready_weight = min(stats.quote_ready_count, 100) * 1.75
    submitted_weight = min(stats.submitted_count, 50) * 2.50
    error_penalty = min(stats.error_count, 100) * 1.20

    freshness_bonus = 0.0
    if stats.last_success_at:
        last_success = parse_dt(stats.last_success_at)
        if last_success:
            hours_ago = max((utcnow() - last_success).total_seconds() / 3600.0, 0.0)
            freshness_bonus = max(0.0, 10.0 - min(hours_ago, 10.0))

    volume_bonus = math.log1p(max(stats.average_items_per_run, 0.0)) * 5.0

    score = harvested_weight + quote_ready_weight + submitted_weight + freshness_bonus + volume_bonus - error_penalty
    return round(clamp(score, 0.0, 1000.0), 2)


def recommend_crawl_interval_minutes(stats: SourceStats) -> int:
    """
    Recommend crawl interval based on priority score.
    """
    score = stats.priority_score

    if score >= 120:
        return 15
    if score >= 80:
        return 30
    if score >= 45:
        return 60
    if score >= 20:
        return 120
    return 240


def should_crawl_now(stats: SourceStats, now: Optional[datetime] = None) -> bool:
    """
    Decide if a source is due for crawling.
    """
    now = now or utcnow()

    if not stats.last_checked_at:
        return True

    last_checked = parse_dt(stats.last_checked_at)
    if not last_checked:
        return True

    next_due = last_checked + timedelta(minutes=stats.crawl_interval_minutes)
    return now >= next_due


def merge_run_result(
    current: Optional[Dict[str, Any]],
    *,
    source: str,
    harvested_count: int,
    quote_ready_count: int = 0,
    submitted_count: int = 0,
    had_error: bool = False,
) -> Dict[str, Any]:
    """
    Update and return one source's performance snapshot.
    """
    previous_runs = 0
    previous_avg = 0.0

    if current:
        previous_runs = int(current.get("runs", 0))
        previous_avg = float(current.get("average_items_per_run", 0.0))

    new_runs = previous_runs + 1
    new_avg = ((previous_avg * previous_runs) + harvested_count) / max(new_runs, 1)

    payload = {
        "source": source,
        "runs": new_runs,
        "harvested_count": int(current.get("harvested_count", 0)) + harvested_count if current else harvested_count,
        "quote_ready_count": int(current.get("quote_ready_count", 0)) + quote_ready_count if current else quote_ready_count,
        "submitted_count": int(current.get("submitted_count", 0)) + submitted_count if current else submitted_count,
        "error_count": int(current.get("error_count", 0)) + (1 if had_error else 0) if current else (1 if had_error else 0),
        "last_checked_at": to_iso(utcnow()),
        "last_success_at": to_iso(utcnow()) if not had_error else (current.get("last_success_at") if current else None),
        "last_deadline_seen_at": current.get("last_deadline_seen_at") if current else None,
        "average_items_per_run": round(new_avg, 2),
    }

    stats = SourceStats(
        source=payload["source"],
        harvested_count=payload["harvested_count"],
        quote_ready_count=payload["quote_ready_count"],
        submitted_count=payload["submitted_count"],
        error_count=payload["error_count"],
        last_checked_at=payload["last_checked_at"],
        last_success_at=payload["last_success_at"],
        last_deadline_seen_at=payload["last_deadline_seen_at"],
        average_items_per_run=payload["average_items_per_run"],
    )

    stats.priority_score = compute_priority_score(stats)
    stats.crawl_interval_minutes = recommend_crawl_interval_minutes(stats)

    final_payload = asdict(stats)
    final_payload["runs"] = new_runs
    return final_payload


def select_sources_to_crawl(
    sources: List[Dict[str, Any]],
    source_metrics: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    From a source list, return only sources that are due to be crawled now.
    Expected source structure:
    [
        {"name": "National Treasury eTenders", "url": "https://..."},
        {"name": "SANRAL", "url": "https://..."},
    ]
    """
    now = utcnow()
    selected: List[Dict[str, Any]] = []

    for source in sources:
        source_name = source.get("name") or source.get("url") or "unknown-source"
        metric = source_metrics.get(source_name)

        if not metric:
            selected.append(source)
            continue

        stats = SourceStats(
            source=metric.get("source", source_name),
            harvested_count=int(metric.get("harvested_count", 0)),
            quote_ready_count=int(metric.get("quote_ready_count", 0)),
            submitted_count=int(metric.get("submitted_count", 0)),
            error_count=int(metric.get("error_count", 0)),
            last_checked_at=metric.get("last_checked_at"),
            last_success_at=metric.get("last_success_at"),
            last_deadline_seen_at=metric.get("last_deadline_seen_at"),
            average_items_per_run=float(metric.get("average_items_per_run", 0.0)),
            priority_score=float(metric.get("priority_score", 0.0)),
            crawl_interval_minutes=int(metric.get("crawl_interval_minutes", 60)),
        )

        if should_crawl_now(stats, now=now):
            selected.append(source)

    return selected


def summarize_source_yield(source_metrics: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Return sorted source-yield summary rows.
    """
    rows: List[Dict[str, Any]] = []

    for source_name, metric in source_metrics.items():
        rows.append(
            {
                "source": source_name,
                "harvested_count": int(metric.get("harvested_count", 0)),
                "quote_ready_count": int(metric.get("quote_ready_count", 0)),
                "submitted_count": int(metric.get("submitted_count", 0)),
                "error_count": int(metric.get("error_count", 0)),
                "average_items_per_run": float(metric.get("average_items_per_run", 0.0)),
                "priority_score": float(metric.get("priority_score", 0.0)),
                "crawl_interval_minutes": int(metric.get("crawl_interval_minutes", 60)),
                "last_checked_at": metric.get("last_checked_at"),
            }
        )

    rows.sort(
        key=lambda row: (
            row["priority_score"],
            row["quote_ready_count"],
            row["harvested_count"],
        ),
        reverse=True,
    )
    return rows
