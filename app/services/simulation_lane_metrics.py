# app/services/simulation_lane_metrics.py

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, asdict
from typing import Any, Dict, List


@dataclass
class LaneMetrics:
    lane: str
    total_count: int
    qualified_count: int
    rejected_count: int
    submission_packs_generated: int
    submission_pack_ready_count: int
    submission_pack_blocked_count: int
    submission_pack_success_rate: float
    submission_pack_block_rate: float
    average_readiness_score: float
    approval_gate_bypass_count: int
    submission_ready_without_approval_count: int
    audit_events_missing: int
    duplicate_audit_events: int
    orphaned_audit_events: int
    top_rejection_codes: List[Dict[str, Any]]
    top_blocking_codes: List[Dict[str, Any]]


def classify_simulation_lane(result: Dict[str, Any]) -> str:
    """
    Lane A: Eligible complete RFQs
    Lane B: Eligible but blocked RFQs
    Lane C: Rejected RFQs
    Lane D: Not recommended RFQs
    Lane E: Edge cases
    """

    qualified = bool(result.get("qualified"))
    rejected = bool(result.get("rejected"))
    approval_ready = bool(result.get("approval_ready"))
    blocking_codes = result.get("blocking_codes") or []
    rejection_codes = result.get("rejection_codes") or []

    if rejected or rejection_codes:
        return "lane_c_rejected"

    if qualified and approval_ready and not blocking_codes:
        return "lane_a_eligible_complete"

    if qualified and blocking_codes:
        return "lane_b_eligible_blocked"

    if not qualified and not rejected and not rejection_codes:
        return "lane_d_not_recommended"

    return "lane_e_edge_cases"


def calculate_lane_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    grouped: Dict[str, List[Dict[str, Any]]] = {
        "lane_a_eligible_complete": [],
        "lane_b_eligible_blocked": [],
        "lane_c_rejected": [],
        "lane_d_not_recommended": [],
        "lane_e_edge_cases": [],
    }

    for result in results:
        lane = classify_simulation_lane(result)
        grouped[lane].append(result)

    lane_metrics = {}

    for lane, lane_results in grouped.items():
        lane_metrics[lane] = asdict(_calculate_single_lane_metrics(lane, lane_results))

    return {
        "lane_metrics": lane_metrics,
        "summary": {
            "total_rfqs": len(results),
            "lane_a_count": len(grouped["lane_a_eligible_complete"]),
            "lane_b_count": len(grouped["lane_b_eligible_blocked"]),
            "lane_c_count": len(grouped["lane_c_rejected"]),
            "lane_d_count": len(grouped["lane_d_not_recommended"]),
            "lane_e_count": len(grouped["lane_e_edge_cases"]),
        },
    }


def _calculate_single_lane_metrics(
    lane: str,
    results: List[Dict[str, Any]],
) -> LaneMetrics:
    total = len(results)

    if total == 0:
        return LaneMetrics(
            lane=lane,
            total_count=0,
            qualified_count=0,
            rejected_count=0,
            submission_packs_generated=0,
            submission_pack_ready_count=0,
            submission_pack_blocked_count=0,
            submission_pack_success_rate=0.0,
            submission_pack_block_rate=0.0,
            average_readiness_score=0.0,
            approval_gate_bypass_count=0,
            submission_ready_without_approval_count=0,
            audit_events_missing=0,
            duplicate_audit_events=0,
            orphaned_audit_events=0,
            top_rejection_codes=[],
            top_blocking_codes=[],
        )

    qualified_count = sum(1 for r in results if r.get("qualified") is True)
    rejected_count = sum(1 for r in results if r.get("rejected") is True)

    submission_packs_generated = sum(
        1 
        for r in results
        if r.get("submission_pack_generated") is True
        or r.get("submission_pack_created") is True
    )
    
    submission_pack_ready_count = sum(
        1
        for r in results
        if r.get("approval_ready") is True and not r.get("blocking_codes")
    )

    submission_pack_blocked_count = sum(
        1 for r in results if bool(r.get("blocking_codes"))
    )

    readiness_scores = [
        float(r.get("readiness_score", 0) or r.get("submission_pack_readiness_score", 0) or 0)
        for r in results
        if r.get("submission_pack_generated") is True
        or r.get("submission_pack_created") is True
    ]
    
    average_readiness_score = (
        round(sum(readiness_scores) / len(readiness_scores), 2)
        if readiness_scores
        else 0.0
    )

    approval_gate_bypass_count = sum(
        1
        for r in results
        if r.get("submission_ready") is True
        and not (
            r.get("approved_by")
            and r.get("approved_at")
            and r.get("approval_decision") == "approved"
        )
    )

    submission_ready_without_approval_count = approval_gate_bypass_count

    audit_events_missing = sum(int(r.get("audit_events_missing", 0) or 0) for r in results)
    duplicate_audit_events = sum(int(r.get("duplicate_audit_events", 0) or 0) for r in results)
    orphaned_audit_events = sum(int(r.get("orphaned_audit_events", 0) or 0) for r in results)

    rejection_counter = Counter()
    blocking_counter = Counter()

    for result in results:
        rejection_counter.update(result.get("rejection_codes") or [])
        blocking_counter.update(result.get("blocking_codes") or [])

    return LaneMetrics(
        lane=lane,
        total_count=total,
        qualified_count=qualified_count,
        rejected_count=rejected_count,
        submission_packs_generated=submission_packs_generated,
        submission_pack_ready_count=submission_pack_ready_count,
        submission_pack_blocked_count=submission_pack_blocked_count,
        submission_pack_success_rate=_percentage(submission_pack_ready_count, total),
        submission_pack_block_rate=_percentage(submission_pack_blocked_count, total),
        average_readiness_score=average_readiness_score,
        approval_gate_bypass_count=approval_gate_bypass_count,
        submission_ready_without_approval_count=submission_ready_without_approval_count,
        audit_events_missing=audit_events_missing,
        duplicate_audit_events=duplicate_audit_events,
        orphaned_audit_events=orphaned_audit_events,
        top_rejection_codes=_top_codes(rejection_counter),
        top_blocking_codes=_top_codes(blocking_counter),
    )


def _percentage(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((value / total) * 100, 2)


def _top_codes(counter: Counter, limit: int = 10) -> List[Dict[str, Any]]:
    return [
        {"code": code, "count": count}
        for code, count in counter.most_common(limit)
    ]
