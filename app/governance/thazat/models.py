from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class _StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class OpportunityDecision(_StrEnum):
    GO = "GO"
    HOLD = "HOLD"
    NO_GO = "NO_GO"


class ExecutionDecision(_StrEnum):
    SUBMIT = "SUBMIT"
    WITHDRAW = "WITHDRAW"
    ESCALATE = "ESCALATE"
    PENDING = "PENDING"


class EvidenceStatus(_StrEnum):
    PROVEN = "PROVEN"
    GAP = "GAP"
    DEVIATION = "DEVIATION"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class IssueStatus(_StrEnum):
    BLOCKER = "BLOCKER"
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"
    CLOSED = "CLOSED"


class RedTeamStatus(_StrEnum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    FAILED = "FAILED"
    PASSED = "PASSED"


class OutcomeResult(_StrEnum):
    WON = "WON"
    LOST = "LOST"
    DISQUALIFIED = "DISQUALIFIED"
    WITHDRAWN = "WITHDRAWN"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class LossReason(_StrEnum):
    PRICE = "PRICE"
    COMPLIANCE = "COMPLIANCE"
    FUNCTIONALITY = "FUNCTIONALITY"
    DELIVERY = "DELIVERY"
    PREFERENCE = "PREFERENCE"
    EVIDENCE = "EVIDENCE"
    BUYER_HISTORY = "BUYER_HISTORY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RequirementEvidence:
    requirement_id: str
    description: str
    mandatory: bool = False
    status: EvidenceStatus = EvidenceStatus.GAP
    evidence_refs: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class GovernanceIssue:
    issue_id: str
    title: str
    status: IssueStatus
    owner: str = ""
    due_at: str = ""
    related_requirement_id: str = ""
    notes: str = ""

    def validate(self) -> None:
        if self.status == IssueStatus.BLOCKER and (not self.owner.strip() or not self.due_at.strip()):
            raise ValueError("Active BLOCKER issues require both owner and due_at")


@dataclass(frozen=True)
class CommercialPosition:
    supplier_cost: float = 0.0
    landed_cost: float = 0.0
    bid_price: float = 0.0
    expected_gp: float = 0.0
    expected_margin_ratio: float = 0.0

    @classmethod
    def from_values(
        cls,
        *,
        landed_cost: float,
        bid_price: float,
        supplier_cost: float = 0.0,
    ) -> "CommercialPosition":
        landed = max(float(landed_cost or 0.0), 0.0)
        bid = max(float(bid_price or 0.0), 0.0)
        gp = bid - landed
        margin = gp / bid if bid > 0 else 0.0
        return cls(
            supplier_cost=max(float(supplier_cost or 0.0), 0.0),
            landed_cost=landed,
            bid_price=bid,
            expected_gp=round(gp, 2),
            expected_margin_ratio=round(margin, 6),
        )


@dataclass(frozen=True)
class ReadinessSnapshot:
    compliance_percent: float
    mandatory_evidence_percent: float
    supplier_coverage_percent: float
    pricing_percent: float
    documents_percent: float
    blocker_count: int
    expected_gp: float
    expected_margin_percent: float
    red_team_status: RedTeamStatus
    overall_readiness_percent: float
    submission_ready: bool
    execution_decision: ExecutionDecision
    reason_codes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "compliance_percent": self.compliance_percent,
            "mandatory_evidence_percent": self.mandatory_evidence_percent,
            "supplier_coverage_percent": self.supplier_coverage_percent,
            "pricing_percent": self.pricing_percent,
            "documents_percent": self.documents_percent,
            "blocker_count": self.blocker_count,
            "expected_gp": self.expected_gp,
            "expected_margin_percent": self.expected_margin_percent,
            "red_team_status": self.red_team_status.value,
            "overall_readiness_percent": self.overall_readiness_percent,
            "submission_ready": self.submission_ready,
            "execution_decision": self.execution_decision.value,
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True)
class OpportunityAssessment:
    decision: OpportunityDecision
    reason_codes: List[str]
    actions: List[str]
    required_margin_percent: float
    minimum_profit: float
    supplier_outreach_required: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason_codes": list(self.reason_codes),
            "actions": list(self.actions),
            "required_margin_percent": self.required_margin_percent,
            "minimum_profit": self.minimum_profit,
            "supplier_outreach_required": self.supplier_outreach_required,
        }


@dataclass(frozen=True)
class OutcomeLearning:
    result: OutcomeResult
    loss_reason: LossReason
    bid_price: float
    winning_price: Optional[float]
    price_delta_value: Optional[float]
    price_delta_percent: Optional[float]
    signals: List[str]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "result": self.result.value,
            "loss_reason": self.loss_reason.value,
            "bid_price": self.bid_price,
            "winning_price": self.winning_price,
            "price_delta_value": self.price_delta_value,
            "price_delta_percent": self.price_delta_percent,
            "signals": list(self.signals),
        }
