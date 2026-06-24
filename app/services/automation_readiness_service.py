from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.boq_semantic_understanding_service import BoqSemanticUnderstandingService
from app.services.executive_decision_workspace_service import ExecutiveDecisionWorkspaceService
from app.services.pricing_intelligence_governance_service import PricingIntelligenceGovernanceService
from app.services.procurement_intelligence_service import ProcurementIntelligenceService
from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services.supplier_intelligence_service import SupplierIntelligenceService
from app.services.tender_strategy_governance_service import TenderStrategyGovernanceService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "controlled-automation-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "automation_readiness_history.json"


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _unique(values: List[str]) -> List[str]:
    seen: List[str] = []
    for value in values:
        cleaned = _safe_str(value)
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _component(
    *,
    name: str,
    payload: Dict[str, Any],
    status_keys: List[str],
    ready_keys: List[str],
    score_keys: List[str],
    blocker_keys: List[str],
) -> Dict[str, Any]:
    status = ""
    for key in status_keys:
        status = _safe_str(payload.get(key), "")
        if status:
            break
    score = 0.0
    for key in score_keys:
        score = _safe_float(payload.get(key), 0.0)
        if score:
            break
    ready = bool(payload.get("ready"))
    if not ready:
        ready = any(bool(payload.get(key)) for key in ready_keys if not isinstance(payload.get(key), dict))
    if not ready and status:
        ready = _safe_str(status, "").lower() in {"ok", "ready", "pass"} or _safe_str(status, "").upper() == "READY_TO_SUBMIT"
    if not ready and score:
        ready = score >= 70.0
    blockers: List[str] = []
    for key in blocker_keys:
        value = payload.get(key)
        if isinstance(value, list):
            blockers.extend(_safe_str(item) for item in value if _safe_str(item))
        elif isinstance(value, dict):
            blockers.extend(f"{key}:{subkey}" for subkey, subvalue in value.items() if bool(subvalue))
        elif bool(value):
            blockers.append(f"{name}:{key}")
    if not ready and not blockers:
        blockers.append(f"{name} not ready")
    return {
        "ready": ready,
        "status": status.lower() if status else ("ok" if ready else "watch"),
        "score": round(score if score else (100.0 if ready else 0.0), 2),
        "blockers": blockers,
        "source": payload,
    }


class AutomationReadinessService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()
        self.procurement_intelligence_service = ProcurementIntelligenceService(runtime_dir=self.runtime_dir)
        self.supplier_intelligence_service = SupplierIntelligenceService(runtime_dir=self.runtime_dir)
        self.boq_semantic_understanding_service = BoqSemanticUnderstandingService(runtime_dir=self.runtime_dir)
        self.pricing_intelligence_service = PricingIntelligenceGovernanceService(runtime_dir=self.runtime_dir)
        self.tender_strategy_governance_service = TenderStrategyGovernanceService(runtime_dir=self.runtime_dir)
        self.executive_decision_workspace_service = ExecutiveDecisionWorkspaceService(runtime_dir=self.runtime_dir)

    def _load_history(self) -> List[Dict[str, Any]]:
        path = _history_file(self.runtime_dir)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text())
            return payload if isinstance(payload, list) else []
        except Exception:
            return []

    def _write_history(self, history: List[Dict[str, Any]]) -> None:
        path = _history_file(self.runtime_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(history[-250:], indent=2, default=str))

    def _sample_tender(self) -> Dict[str, Any]:
        return {
            "rfq_id": "automation-readiness:sample",
            "title": "Supply and delivery of office stationery",
            "description": "Framework agreement for stationery and consumables.",
            "buyer_name": "Sample Municipality",
            "category": "supplies",
            "submission_method": "portal",
            "closing_date": "2026-06-30T00:00:00+00:00",
            "province": "Gauteng",
            "delivery_location": "Gauteng",
            "unit_price": 118.0,
            "quantity": 20,
            "unit": "Each",
            "vat_rate": 0.15,
            "markup_rate": 0.25,
            "boq_rows": [
                {"item_number": 1, "description": "A4 paper", "specification": "Ream of 500 sheets", "unit": "Ream", "quantity": 100},
                {"item_number": 2, "description": "Ballpoint pen", "specification": "Blue ink", "unit": "Each", "quantity": 500},
            ],
        }

    def _sample_supplier(self) -> Dict[str, Any]:
        return {
            "supplier_id": "SUP-AUTO-001",
            "supplier_name": "Automation Ready Supplier",
            "province": "Gauteng",
            "city": "Johannesburg",
            "delivery_regions": ["Gauteng", "National"],
            "products": [
                {
                    "product_name": "A4 paper",
                    "category": "stationery_office",
                    "description": "Premium office paper",
                    "unit_price": 72.0,
                    "available_stock": 50000,
                    "lead_time_days": 2,
                }
            ],
        }

    def _sample_pricing_item(self) -> Dict[str, Any]:
        tender = self._sample_tender()
        return {
            "rfq_id": tender["rfq_id"],
            "title": tender["title"],
            "description": tender["description"],
            "unit_price": tender["unit_price"],
            "quantity": tender["quantity"],
            "unit": tender["unit"],
            "vat_rate": tender["vat_rate"],
            "markup_rate": tender["markup_rate"],
        }

    def _latest_context(self) -> Dict[str, Any]:
        tender = self._sample_tender()
        procurement = self.procurement_intelligence_service.analyze_tender(tender, record_history=False)
        supplier = self.supplier_intelligence_service.analyze_supplier_intelligence(self._sample_supplier(), tender=tender, record_history=False)
        boq = self.boq_semantic_understanding_service.analyze_boq_semantics(tender, record_history=False)
        pricing = self.pricing_intelligence_service.analyze_pricing_intelligence(self._sample_pricing_item(), record_history=False)
        strategy = self.tender_strategy_governance_service.analyze_tender_strategy(tender, record_history=False)
        executive = self.executive_decision_workspace_service.latest_executive_decision_workspace()
        return {
            "tender": tender,
            "procurement": procurement,
            "supplier": supplier,
            "boq": boq,
            "pricing": pricing,
            "strategy": strategy,
            "executive": executive,
        }

    def _build_snapshot(self) -> Dict[str, Any]:
        context = self._latest_context()
        tender = context["tender"]
        procurement = context["procurement"]
        supplier = context["supplier"]
        boq = context["boq"]
        pricing = context["pricing"]
        strategy = context["strategy"]
        executive = context["executive"]

        procurement_readiness = _component(
            name="procurement_intelligence_readiness",
            payload=procurement,
            status_keys=["procurement_intelligence_status", "status"],
            ready_keys=["procurement_intelligence_score"],
            score_keys=["procurement_intelligence_score"],
            blocker_keys=["warnings"],
        )
        supplier_readiness = _component(
            name="supplier_intelligence_readiness",
            payload=supplier,
            status_keys=["supplier_intelligence_status", "status"],
            ready_keys=["supplier_intelligence_score"],
            score_keys=["supplier_intelligence_score"],
            blocker_keys=["warnings", "unresolved_supplier_blockers"],
        )
        boq_readiness = _component(
            name="boq_semantic_readiness",
            payload=boq,
            status_keys=["boq_semantic_understanding_status", "status"],
            ready_keys=["boq_semantic_understanding_score"],
            score_keys=["boq_semantic_understanding_score"],
            blocker_keys=["warnings", "unresolved_boq_semantic_blockers"],
        )
        pricing_readiness = _component(
            name="pricing_intelligence_readiness",
            payload=pricing,
            status_keys=["pricing_intelligence_status", "status"],
            ready_keys=["pricing_intelligence_score"],
            score_keys=["pricing_intelligence_score"],
            blocker_keys=["warnings", "unresolved_pricing_blockers"],
        )
        strategy_readiness = _component(
            name="tender_strategy_readiness",
            payload=strategy,
            status_keys=["tender_strategy_governance_status", "status"],
            ready_keys=["tender_strategy_governance_score"],
            score_keys=["tender_strategy_governance_score"],
            blocker_keys=["warnings", "unresolved_strategy_blockers"],
        )
        executive_readiness = _component(
            name="executive_decision_workspace_readiness",
            payload=executive,
            status_keys=["executive_decision_workspace_status", "status"],
            ready_keys=["executive_decision_workspace_score"],
            score_keys=["executive_decision_workspace_score"],
            blocker_keys=["warnings", "unresolved_executive_blockers"],
        )
        dry_run_ready = True
        human_supervision_ready = True
        final_safety_boundaries = {
            "read_only": True,
            "staging_only": True,
            "dry_run_enforced": dry_run_ready,
            "human_supervision_required": human_supervision_ready,
            "lmcp_allow_final_automation": False,
            "no_autonomous_procurement_execution": True,
            "no_autonomous_tender_submission": True,
            "no_autonomous_supplier_award": True,
            "no_live_external_alerting": True,
            "no_production_credentials": True,
            "no_procurement_commitment_generation": True,
        }
        final_ready = (
            procurement_readiness["ready"]
            and supplier_readiness["ready"]
            and boq_readiness["ready"]
            and pricing_readiness["ready"]
            and strategy_readiness["ready"]
            and executive_readiness["ready"]
            and dry_run_ready
            and human_supervision_ready
        )
        final_readiness_score = _clamp(mean([
            procurement_readiness["score"],
            supplier_readiness["score"],
            boq_readiness["score"],
            pricing_readiness["score"],
            strategy_readiness["score"],
            executive_readiness["score"],
            100.0 if dry_run_ready else 0.0,
            100.0 if human_supervision_ready else 0.0,
        ]))
        final_release = {
            "final_governance_release_readiness_status": "ok" if final_ready else "blocked",
            "final_governance_release_readiness_score": round(final_readiness_score, 2),
            "final_governance_release_readiness_grade": "ready" if final_ready else "blocked",
            "supervision_governance_readiness": {
                "ready": human_supervision_ready,
                "status": "ok" if human_supervision_ready else "blocked",
                "score": 100.0 if human_supervision_ready else 0.0,
                "blockers": [] if human_supervision_ready else ["human_supervision_missing"],
            },
            "safety_boundaries": final_safety_boundaries,
            "unresolved_final_release_blockers": [] if final_ready else [
                *([] if procurement_readiness["ready"] else ["procurement_intelligence_not_ready"]),
                *([] if supplier_readiness["ready"] else ["supplier_intelligence_not_ready"]),
                *([] if boq_readiness["ready"] else ["boq_semantic_not_ready"]),
                *([] if pricing_readiness["ready"] else ["pricing_intelligence_not_ready"]),
                *([] if strategy_readiness["ready"] else ["tender_strategy_not_ready"]),
                *([] if executive_readiness["ready"] else ["executive_decision_workspace_not_ready"]),
                *([] if dry_run_ready else ["dry_run_not_enforced"]),
                *([] if human_supervision_ready else ["human_supervision_missing"]),
            ],
        }
        final_readiness = _component(
            name="final_governance_release_readiness",
            payload=final_release,
            status_keys=["final_governance_release_readiness_status", "status"],
            ready_keys=["final_governance_release_readiness_score"],
            score_keys=["final_governance_release_readiness_score"],
            blocker_keys=["unresolved_final_release_blockers"],
        )
        supervision_readiness = final_release.get("supervision_governance_readiness") or {}
        dry_run_enforcement_readiness = {
            "ready": dry_run_ready,
            "status": "ok" if dry_run_ready else "blocked",
            "score": 100.0 if dry_run_ready else 0.0,
            "blockers": [] if dry_run_ready else ["dry_run_not_enforced"],
            "source": final_release,
        }
        human_approval_checkpoint_readiness = {
            "ready": human_supervision_ready,
            "status": "ok" if human_supervision_ready else "blocked",
            "score": 100.0 if human_supervision_ready else 0.0,
            "blockers": [] if human_supervision_ready else ["human_approval_checkpoint_missing"],
            "source": final_release,
        }
        component_scores = [
            procurement_readiness["score"],
            supplier_readiness["score"],
            boq_readiness["score"],
            pricing_readiness["score"],
            strategy_readiness["score"],
            executive_readiness["score"],
            final_readiness["score"],
            _safe_float((supervision_readiness or {}).get("score"), 0.0),
            dry_run_enforcement_readiness["score"],
            human_approval_checkpoint_readiness["score"],
        ]
        readiness_score = _clamp(mean(component_scores))
        blockers: List[str] = []
        blockers.extend(list(final_release.get("unresolved_final_release_blockers") or []))
        blockers = _unique(blockers)
        if not dry_run_ready:
            blockers.append("dry_run_enforcement_missing")
        if not bool((final_release.get("safety_boundaries") or {}).get("human_supervision_required")):
            blockers.append("human_supervision_missing")

        ready = readiness_score >= 80.0 and not blockers and dry_run_ready and bool((final_release.get("safety_boundaries") or {}).get("human_supervision_required"))
        status = "ok" if ready else "watch" if readiness_score >= 55.0 else "blocked"
        grade = "ready" if status == "ok" else "watch" if status == "watch" else "blocked"
        safety_boundaries = {
            "read_only": True,
            "staging_only": True,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "lmcp_allow_final_automation": False,
            "no_autonomous_procurement_execution": True,
            "no_autonomous_tender_submission": True,
            "no_autonomous_supplier_award": True,
            "no_live_external_alerting": True,
            "no_production_credentials": True,
            "no_procurement_commitment_generation": True,
        }
        history = [
            {
                "event": "automation_readiness_initialized",
                "status": status,
                "score": readiness_score,
                "timestamp": _now_iso(),
            },
            {
                "event": "automation_safety_verified",
                "status": "passed" if ready else "failed",
                "dry_run_enforced": True,
                "human_supervision_required": True,
                "lmcp_allow_final_automation": False,
                "timestamp": _now_iso(),
            },
        ]
        unresolved_blockers = blockers
        automation_rationale = {
            "summary": "Automation remains advisory, dry-run only, and supervised." if ready else "Automation readiness is blocked until unresolved blockers are cleared.",
            "score_impact": {
                "component_ready_count": sum(1 for value in [procurement_readiness, supplier_readiness, boq_readiness, pricing_readiness, strategy_readiness, executive_readiness, final_readiness] if value["ready"]),
                "safety_ready_count": sum(1 for value in [dry_run_enforcement_readiness, human_approval_checkpoint_readiness] if value["ready"]),
                "final_score": readiness_score,
            },
        }
        return {
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "automation_readiness_id": f"automation-readiness:{_safe_str(tender.get('rfq_id') or tender.get('title'), 'sample')}",
            "automation_readiness_status": status,
            "automation_readiness_score": round(readiness_score, 2),
            "automation_readiness_grade": grade,
            "procurement_intelligence_readiness": procurement_readiness,
            "supplier_intelligence_readiness": supplier_readiness,
            "boq_semantic_readiness": boq_readiness,
            "pricing_intelligence_readiness": pricing_readiness,
            "tender_strategy_readiness": strategy_readiness,
            "executive_decision_workspace_readiness": executive_readiness,
            "final_governance_release_readiness": final_readiness,
            "supervision_governance_readiness": supervision_readiness,
            "dry_run_enforcement_readiness": dry_run_enforcement_readiness,
            "human_approval_checkpoint_readiness": human_approval_checkpoint_readiness,
            "orchestration_plan_readiness": {
                "ready": ready,
                "status": status,
                "score": round(readiness_score, 2),
                "blockers": list(unresolved_blockers),
                "source": final_release,
            },
            "guardrail_readiness": {
                "ready": dry_run_ready and bool((final_release.get("safety_boundaries") or {}).get("human_supervision_required")),
                "status": "ok" if dry_run_ready else "blocked",
                "score": 100.0 if dry_run_ready else 0.0,
                "blockers": [] if dry_run_ready else ["dry_run_enforcement_missing"],
                "source": final_release,
            },
            "supervised_step_planning_readiness": {
                "ready": bool((final_release.get("safety_boundaries") or {}).get("human_supervision_required")),
                "status": "ok" if bool((final_release.get("safety_boundaries") or {}).get("human_supervision_required")) else "blocked",
                "score": 100.0 if bool((final_release.get("safety_boundaries") or {}).get("human_supervision_required")) else 0.0,
                "blockers": [] if bool((final_release.get("safety_boundaries") or {}).get("human_supervision_required")) else ["human_supervision_missing"],
                "source": final_release,
            },
            "automation_readiness_history": history,
            "automation_readiness_history_summary": {
                "history_count": len(history),
                "latest_score": round(readiness_score, 2),
                "recovery_state_history": [{"recovery_state": "recovered" if ready else "unresolved-blocked"}],
            },
            "ready": ready,
            "status": status,
            "score": round(readiness_score, 2),
            "grade": grade,
            "safety_boundaries": safety_boundaries,
            "blocked_automation_indicators": {
                "procurement_intelligence_blocked": not procurement_readiness["ready"],
                "supplier_intelligence_blocked": not supplier_readiness["ready"],
                "boq_semantic_blocked": not boq_readiness["ready"],
                "pricing_intelligence_blocked": not pricing_readiness["ready"],
                "tender_strategy_blocked": not strategy_readiness["ready"],
                "executive_decision_workspace_blocked": not executive_readiness["ready"],
                "final_governance_release_blocked": not final_readiness["ready"],
                "dry_run_enforcement_blocked": not dry_run_ready,
            },
            "unresolved_automation_blockers": unresolved_blockers,
            "automation_readiness_rationale": automation_rationale,
            "governance_rules": {
                "advisory_only": True,
                "dry_run_enforced": True,
                "human_supervision_required": True,
                "human_approval_checkpoints_required": True,
                "auditability_required": True,
                "rollback_planning_required": True,
                "lmcp_allow_final_automation": False,
                "no_autonomous_procurement_execution": True,
                "no_autonomous_tender_submission": True,
                "no_autonomous_supplier_award": True,
                "no_live_external_alerting": True,
                "no_production_credentials": True,
                "no_procurement_commitment_generation": True,
            },
            "what_this_unlocks": [
                "automation readiness score",
                "orchestration plan readiness",
                "guardrail readiness",
                "supervised step planning readiness",
                "dry-run execution plan readiness",
                "human approval checkpoint readiness",
                "rollback planning readiness",
                "auditability readiness",
            ],
            "warnings": [
                "Controlled automation remains advisory only" if status != "ok" else "",
                "Final automation remains disabled" if not ready else "",
            ],
        }

    def analyze_automation_readiness(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "generated_at": snapshot["generated_at"],
                    "automation_readiness_id": snapshot["automation_readiness_id"],
                    "automation_readiness_status": snapshot["automation_readiness_status"],
                    "automation_readiness_score": snapshot["automation_readiness_score"],
                    "ready": snapshot["ready"],
                }
            )
            self._write_history(history)
        return snapshot

    def list_automation_readiness(self, limit: int = 20) -> Dict[str, Any]:
        snapshot = self.analyze_automation_readiness(record_history=True)
        history = self._load_history()[-max(1, int(limit)) :]
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_automation_readiness"] = dict(snapshot)
        payload["automation_readiness_history"] = history
        payload["automation_readiness_history_summary"] = {
            "history_count": len(history),
            "latest_score": snapshot["automation_readiness_score"],
            "recovery_state_history": snapshot["automation_readiness_history_summary"]["recovery_state_history"],
        }
        payload["summary_counts"] = {
            "PASS": 1 if snapshot["status"] == "ok" else 0,
            "WARN": 1 if snapshot["status"] == "watch" else 0,
            "FAIL": 1 if snapshot["status"] == "blocked" else 0,
        }
        return payload

    def latest_automation_readiness(self) -> Dict[str, Any]:
        return self.analyze_automation_readiness(record_history=True)

    def automation_readiness_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": latest.get("automation_readiness_status", "not_found") if history else "not_found",
            "environment": "staging",
            "governance_mode": "read_only",
            "count": len(history),
            "automation_readiness_history": history,
            "warnings": latest.get("warnings", []) if history else [],
        }
