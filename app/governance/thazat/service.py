from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .models import (
    CommercialPosition,
    EvidenceStatus,
    ExecutionDecision,
    GovernanceIssue,
    IssueStatus,
    LossReason,
    OpportunityAssessment,
    OpportunityDecision,
    OutcomeLearning,
    OutcomeResult,
    ReadinessSnapshot,
    RedTeamStatus,
    RequirementEvidence,
)


MIN_MARGIN_RATIO = 0.25
ESCALATED_MARGIN_RATIO = 0.35
MIN_PROFIT = 25_000.0
DEFAULT_SUPPLIER_TARGET = 3


def _pct(numerator: float, denominator: float, *, empty_value: float = 100.0) -> float:
    if denominator <= 0:
        return float(empty_value)
    return round(max(0.0, min(100.0, (numerator / denominator) * 100.0)), 2)


def _as_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "pass", "passed"}:
        return True
    if text in {"0", "false", "no", "n", "fail", "failed"}:
        return False
    return None


def _enum(enum_type: Any, value: Any, default: Any) -> Any:
    try:
        return enum_type(str(value).strip().upper())
    except Exception:
        return default


def commercial_gate(
    *,
    estimated_profit: float,
    gross_margin_ratio: float,
    recoverable: bool = True,
) -> Dict[str, Any]:
    """Evaluate AMIRI commercial rules without prematurely killing repricing work.

    The standing rule is 25% minimum margin and R25k minimum profit.  If the
    25% case produces less than R25k, THAZAT requests repricing at 35% rather
    than treating the first price as a final rejection.  A position that is
    still below R25k at 35% is uneconomic unless an operator deliberately
    overrides the commercial objective outside this function.
    """

    profit = float(estimated_profit or 0.0)
    margin = float(gross_margin_ratio or 0.0)
    reason_codes: List[str] = []

    required_margin = MIN_MARGIN_RATIO
    requires_escalation = profit < MIN_PROFIT and margin <= MIN_MARGIN_RATIO
    if requires_escalation:
        required_margin = ESCALATED_MARGIN_RATIO
        reason_codes.append("MARGIN_ESCALATION_REQUIRED")

    profit_ok = profit >= MIN_PROFIT
    margin_ok = margin >= required_margin
    viable = profit_ok and margin_ok

    if not profit_ok:
        reason_codes.append("PROFIT_BELOW_MINIMUM")
    if not margin_ok:
        reason_codes.append("MARGIN_BELOW_REQUIRED_LEVEL")

    if viable:
        state = "PASS"
    elif recoverable and (requires_escalation or margin < required_margin):
        state = "REPRICE"
    else:
        state = "FAIL"

    return {
        "state": state,
        "viable": viable,
        "recoverable": bool(recoverable),
        "minimum_profit": MIN_PROFIT,
        "minimum_margin_ratio": MIN_MARGIN_RATIO,
        "required_margin_ratio": required_margin,
        "required_margin_percent": round(required_margin * 100.0, 2),
        "requires_margin_escalation": requires_escalation,
        "profit_ok": profit_ok,
        "margin_ok": margin_ok,
        "reason_codes": reason_codes,
    }


def evaluate_opportunity(payload: Mapping[str, Any]) -> OpportunityAssessment:
    """Apply the THAZAT commercial and hard-governance gate.

    NO_GO is reserved for hard failures. Recoverable uncertainty becomes HOLD
    so LMCP can continue pricing/sourcing rather than confusing missing data
    with a final rejection.
    """

    reasons: List[str] = []
    actions: List[str] = []

    eligibility_ok = _as_bool(payload.get("eligibility_ok"))
    mandatory_evidence_obtainable = _as_bool(payload.get("mandatory_evidence_obtainable"))
    delivery_ok = _as_bool(payload.get("delivery_ok"))
    supply_route_ok = _as_bool(payload.get("supply_route_ok"))
    critical_information_complete = _as_bool(payload.get("critical_information_complete"))
    commercial_recoverable = _as_bool(payload.get("commercial_recoverable"))
    if commercial_recoverable is None:
        commercial_recoverable = True

    commercial = commercial_gate(
        estimated_profit=float(payload.get("estimated_profit") or 0.0),
        gross_margin_ratio=float(payload.get("gross_margin_ratio") or 0.0),
        recoverable=commercial_recoverable,
    )
    reasons.extend(commercial["reason_codes"])

    hard_failures = []
    if eligibility_ok is False:
        hard_failures.append("ELIGIBILITY_FAILED")
    if mandatory_evidence_obtainable is False:
        hard_failures.append("MANDATORY_EVIDENCE_UNOBTAINABLE")
    if delivery_ok is False:
        hard_failures.append("DELIVERY_IMPOSSIBLE")
    if commercial["state"] == "FAIL":
        hard_failures.append("COMMERCIAL_GATE_FAILED")

    if hard_failures:
        decision = OpportunityDecision.NO_GO
        reasons.extend(hard_failures)
        actions.append("CLOSE_OR_WITHDRAW_OPPORTUNITY")
    else:
        hold_reasons = []
        if eligibility_ok is None:
            hold_reasons.append("ELIGIBILITY_UNCONFIRMED")
        if mandatory_evidence_obtainable is None:
            hold_reasons.append("MANDATORY_EVIDENCE_UNCONFIRMED")
        if delivery_ok is None:
            hold_reasons.append("DELIVERY_UNCONFIRMED")
        if supply_route_ok is False:
            hold_reasons.append("SUPPLY_ROUTE_GAP")
        elif supply_route_ok is None:
            hold_reasons.append("SUPPLY_ROUTE_UNCONFIRMED")
        if critical_information_complete is False or critical_information_complete is None:
            hold_reasons.append("CRITICAL_INFORMATION_INCOMPLETE")
        if commercial["state"] == "REPRICE":
            hold_reasons.append("COMMERCIAL_REPRICING_REQUIRED")
            actions.append("REPRICE_TO_REQUIRED_MARGIN")

        reasons.extend(hold_reasons)
        decision = OpportunityDecision.HOLD if hold_reasons else OpportunityDecision.GO

    supplier_quotes_received = int(payload.get("supplier_quotes_received") or 0)
    supplier_target = max(int(payload.get("supplier_target") or DEFAULT_SUPPLIER_TARGET), 1)
    sole_source_documented = bool(payload.get("sole_source_documented", False))
    supplier_outreach_required = (
        decision == OpportunityDecision.GO
        and not sole_source_documented
        and supplier_quotes_received < supplier_target
    )
    if supplier_outreach_required:
        actions.append("START_SUPPLIER_OUTREACH")
    if decision == OpportunityDecision.GO:
        actions.append("BUILD_EVIDENCE_AND_READINESS")

    return OpportunityAssessment(
        decision=decision,
        reason_codes=list(dict.fromkeys(reasons)),
        actions=list(dict.fromkeys(actions)),
        required_margin_percent=float(commercial["required_margin_percent"]),
        minimum_profit=MIN_PROFIT,
        supplier_outreach_required=supplier_outreach_required,
    )


def _requirement_from_mapping(value: Mapping[str, Any]) -> RequirementEvidence:
    return RequirementEvidence(
        requirement_id=str(value.get("requirement_id") or value.get("id") or "").strip(),
        description=str(value.get("description") or value.get("requirement") or "").strip(),
        mandatory=bool(value.get("mandatory", False)),
        status=_enum(EvidenceStatus, value.get("status"), EvidenceStatus.GAP),
        evidence_refs=[str(item) for item in (value.get("evidence_refs") or []) if str(item).strip()],
        notes=str(value.get("notes") or "").strip(),
    )


def _issue_from_mapping(value: Mapping[str, Any]) -> GovernanceIssue:
    issue = GovernanceIssue(
        issue_id=str(value.get("issue_id") or value.get("id") or "").strip(),
        title=str(value.get("title") or "").strip(),
        status=_enum(IssueStatus, value.get("status"), IssueStatus.REQUIRED),
        owner=str(value.get("owner") or "").strip(),
        due_at=str(value.get("due_at") or value.get("deadline") or "").strip(),
        related_requirement_id=str(value.get("related_requirement_id") or "").strip(),
        notes=str(value.get("notes") or "").strip(),
    )
    issue.validate()
    return issue


def calculate_readiness(payload: Mapping[str, Any]) -> ReadinessSnapshot:
    requirements = [
        item if isinstance(item, RequirementEvidence) else _requirement_from_mapping(item)
        for item in (payload.get("requirements") or [])
    ]
    issues = [
        item if isinstance(item, GovernanceIssue) else _issue_from_mapping(item)
        for item in (payload.get("issues") or [])
    ]

    compliant_statuses = {EvidenceStatus.PROVEN, EvidenceStatus.NOT_APPLICABLE}
    compliance_percent = _pct(
        sum(1 for item in requirements if item.status in compliant_statuses),
        len(requirements),
    )
    mandatory = [item for item in requirements if item.mandatory]
    mandatory_evidence_percent = _pct(
        sum(1 for item in mandatory if item.status in compliant_statuses),
        len(mandatory),
    )

    received = max(int(payload.get("supplier_quotes_received") or 0), 0)
    supplier_target = max(int(payload.get("supplier_target") or DEFAULT_SUPPLIER_TARGET), 1)
    sole_source_documented = bool(payload.get("sole_source_documented", False))
    supplier_coverage_percent = 100.0 if sole_source_documented and received >= 1 else _pct(received, supplier_target, empty_value=0.0)

    pricing_percent = _pct(
        max(int(payload.get("priced_items") or 0), 0),
        max(int(payload.get("total_items") or 0), 0),
        empty_value=0.0,
    )
    documents_percent = _pct(
        max(int(payload.get("completed_documents") or 0), 0),
        max(int(payload.get("required_documents") or 0), 0),
        empty_value=100.0,
    )

    blocker_count = sum(1 for issue in issues if issue.status == IssueStatus.BLOCKER)
    red_team_status = _enum(RedTeamStatus, payload.get("red_team_status"), RedTeamStatus.NOT_STARTED)

    if payload.get("commercials"):
        raw_commercials = payload.get("commercials") or {}
        if isinstance(raw_commercials, CommercialPosition):
            commercials = raw_commercials
        else:
            commercials = CommercialPosition.from_values(
                landed_cost=float(raw_commercials.get("landed_cost") or 0.0),
                bid_price=float(raw_commercials.get("bid_price") or 0.0),
                supplier_cost=float(raw_commercials.get("supplier_cost") or 0.0),
            )
    else:
        commercials = CommercialPosition.from_values(
            landed_cost=float(payload.get("landed_cost") or 0.0),
            bid_price=float(payload.get("bid_price") or 0.0),
            supplier_cost=float(payload.get("supplier_cost") or 0.0),
        )

    red_team_component = {
        RedTeamStatus.PASSED: 100.0,
        RedTeamStatus.IN_PROGRESS: 50.0,
        RedTeamStatus.NOT_STARTED: 0.0,
        RedTeamStatus.FAILED: 0.0,
    }[red_team_status]

    overall = (
        compliance_percent * 0.25
        + mandatory_evidence_percent * 0.25
        + supplier_coverage_percent * 0.10
        + pricing_percent * 0.15
        + documents_percent * 0.15
        + red_team_component * 0.10
    )

    reason_codes: List[str] = []
    if blocker_count:
        reason_codes.append("ACTIVE_BLOCKERS")
        overall = min(overall, 89.0)
    if mandatory_evidence_percent < 100.0:
        reason_codes.append("MANDATORY_EVIDENCE_INCOMPLETE")
        overall = min(overall, 89.0)
    if red_team_status != RedTeamStatus.PASSED:
        reason_codes.append("RED_TEAM_NOT_PASSED")
        overall = min(overall, 94.0)
    if pricing_percent < 100.0:
        reason_codes.append("PRICING_INCOMPLETE")
    if documents_percent < 100.0:
        reason_codes.append("DOCUMENTS_INCOMPLETE")
    if supplier_coverage_percent < 100.0:
        reason_codes.append("SUPPLIER_COVERAGE_INCOMPLETE")

    opportunity_decision = _enum(
        OpportunityDecision,
        payload.get("opportunity_decision"),
        OpportunityDecision.HOLD,
    )

    supplier_gate_ok = supplier_coverage_percent >= 100.0 or sole_source_documented
    submission_ready = all(
        [
            opportunity_decision == OpportunityDecision.GO,
            blocker_count == 0,
            mandatory_evidence_percent >= 100.0,
            pricing_percent >= 100.0,
            documents_percent >= 100.0,
            supplier_gate_ok,
            red_team_status == RedTeamStatus.PASSED,
        ]
    )

    if submission_ready:
        execution_decision = ExecutionDecision.SUBMIT
    elif opportunity_decision == OpportunityDecision.NO_GO:
        execution_decision = ExecutionDecision.WITHDRAW
    elif blocker_count or red_team_status == RedTeamStatus.FAILED:
        execution_decision = ExecutionDecision.ESCALATE
    else:
        execution_decision = ExecutionDecision.PENDING

    return ReadinessSnapshot(
        compliance_percent=round(compliance_percent, 2),
        mandatory_evidence_percent=round(mandatory_evidence_percent, 2),
        supplier_coverage_percent=round(supplier_coverage_percent, 2),
        pricing_percent=round(pricing_percent, 2),
        documents_percent=round(documents_percent, 2),
        blocker_count=blocker_count,
        expected_gp=commercials.expected_gp,
        expected_margin_percent=round(commercials.expected_margin_ratio * 100.0, 2),
        red_team_status=red_team_status,
        overall_readiness_percent=round(max(0.0, min(100.0, overall)), 2),
        submission_ready=submission_ready,
        execution_decision=execution_decision,
        reason_codes=reason_codes,
    )


def run_red_team(checks: Mapping[str, Any]) -> Dict[str, Any]:
    """Evaluate disqualification checks; no external submission side effects."""

    normalized: Dict[str, Optional[bool]] = {str(key): _as_bool(value) for key, value in checks.items()}
    failed = sorted(key for key, value in normalized.items() if value is False)
    pending = sorted(key for key, value in normalized.items() if value is None)

    if failed:
        status = RedTeamStatus.FAILED
    elif pending or not normalized:
        status = RedTeamStatus.IN_PROGRESS
    else:
        status = RedTeamStatus.PASSED

    return {
        "status": status.value,
        "failed_checks": failed,
        "pending_checks": pending,
        "submission_gate_passed": status == RedTeamStatus.PASSED,
    }


def build_outcome_learning(payload: Mapping[str, Any]) -> OutcomeLearning:
    result = _enum(OutcomeResult, payload.get("result"), OutcomeResult.UNKNOWN)
    loss_reason = _enum(LossReason, payload.get("loss_reason"), LossReason.UNKNOWN)
    bid_price = float(payload.get("bid_price") or 0.0)
    raw_winning_price = payload.get("winning_price")
    winning_price: Optional[float] = None if raw_winning_price in (None, "") else float(raw_winning_price)

    delta_value: Optional[float] = None
    delta_percent: Optional[float] = None
    signals: List[str] = []

    if winning_price is not None and bid_price > 0:
        delta_value = round(bid_price - winning_price, 2)
        delta_percent = round((delta_value / winning_price) * 100.0, 2) if winning_price > 0 else None
        if result == OutcomeResult.LOST and delta_value > 0:
            signals.append("BID_PRICE_ABOVE_WINNER")
        elif result == OutcomeResult.WON:
            signals.append("WINNING_PRICE_CAPTURED")

    if result == OutcomeResult.DISQUALIFIED:
        signals.append("DISQUALIFICATION_REVIEW_REQUIRED")
    if result == OutcomeResult.LOST and loss_reason == LossReason.UNKNOWN:
        signals.append("LOSS_REASON_RESEARCH_REQUIRED")
    if loss_reason != LossReason.UNKNOWN:
        signals.append(f"LOSS_REASON_{loss_reason.value}")

    return OutcomeLearning(
        result=result,
        loss_reason=loss_reason,
        bid_price=round(bid_price, 2),
        winning_price=None if winning_price is None else round(winning_price, 2),
        price_delta_value=delta_value,
        price_delta_percent=delta_percent,
        signals=list(dict.fromkeys(signals)),
    )
