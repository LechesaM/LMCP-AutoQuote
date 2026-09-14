"""THAZAT(AM)^2 procurement governance primitives.

THAZAT is a governance layer over the existing LMCP execution pipeline.  It
never submits a bid itself; it evaluates decisions, readiness, red-team state,
and outcome-learning signals for operator-controlled workflows.
"""

from .models import (
    EvidenceStatus,
    ExecutionDecision,
    IssueStatus,
    LossReason,
    OpportunityDecision,
    OutcomeResult,
    RedTeamStatus,
)
from .service import (
    build_outcome_learning,
    calculate_readiness,
    commercial_gate,
    evaluate_opportunity,
    run_red_team,
)

__all__ = [
    "EvidenceStatus",
    "ExecutionDecision",
    "IssueStatus",
    "LossReason",
    "OpportunityDecision",
    "OutcomeResult",
    "RedTeamStatus",
    "build_outcome_learning",
    "calculate_readiness",
    "commercial_gate",
    "evaluate_opportunity",
    "run_red_team",
]
