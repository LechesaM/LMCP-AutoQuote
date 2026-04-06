from __future__ import annotations

import importlib
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# =========================================================
# Business rules
# =========================================================
MIN_SCORE_TO_TRIGGER = 75.0
MIN_ESTIMATED_PROFIT = 30_000.0
MIN_MARGIN_PERCENT = 25.0
MIN_HOURS_BEFORE_DEADLINE = 4.0

ALLOWED_QUALIFICATION_STATUS = {"qualified"}
ALLOWED_SUBMISSION_METHODS = {"email", "portal", "physical"}

DEFAULT_DRAFT_STATUS = "pending"
DEFAULT_TRIGGER_SOURCE = "auto_pipeline"


# =========================================================
# Dynamic imports
# =========================================================
def _import_model(module_candidates: List[str], class_name: str) -> Any:
    errors: List[str] = []

    for module_name in module_candidates:
        try:
            module = importlib.import_module(module_name)
            model = getattr(module, class_name)
            return model
        except Exception as e:
            errors.append(f"{module_name}.{class_name} -> {e}")

    raise ImportError(
        f"Could not import {class_name}. Tried:\n" + "\n".join(errors)
    )


def _resolve_quote_draft_model() -> Any:
    return _import_model(
        [
            "app.models.quote_draft",
            "app.models.core",
        ],
        "QuoteDraft",
    )


def _resolve_opportunity_model() -> Any:
    return _import_model(
        [
            "app.models.opportunity",
            "app.models.core",
        ],
        "Opportunity",
    )


def _resolve_pipeline_event_model() -> Optional[Any]:
    candidates = [
        ("app.models.tender_pipeline_event", "TenderPipelineEvent"),
        ("app.models.core", "TenderPipelineEvent"),
    ]
    for module_name, class_name in candidates:
        try:
            module = importlib.import_module(module_name)
            return getattr(module, class_name)
        except Exception:
            continue
    return None


QuoteDraft = _resolve_quote_draft_model()
Opportunity = _resolve_opportunity_model()
TenderPipelineEvent = _resolve_pipeline_event_model()


# =========================================================
# Result model
# =========================================================
@dataclass
class AutoQuoteTriggerResult:
    should_trigger: bool
    triggered: bool
    skipped: bool

    score_total: Optional[float]
    qualification_status: str
    estimated_profit_value: Optional[float]
    assumed_margin_percent: Optional[float]
    submission_method: str
    days_to_deadline: Optional[float]

    reasons: List[str]
    skip_reasons: List[str]
    risk_flags: List[str]

    quote_draft_id: Optional[int]
    quote_draft_status: Optional[str]
    trigger_source: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =========================================================
# Public API
# =========================================================
def should_trigger_auto_quote(opportunity: Any) -> AutoQuoteTriggerResult:
    score_total = _get_float_attr(opportunity, ["score_total"], None)
    qualification_status = _get_first_attr(opportunity, ["qualification_status"], "")
    estimated_profit_value = _get_float_attr(opportunity, ["estimated_profit_value"], None)
    assumed_margin_percent = _get_float_attr(opportunity, ["assumed_margin_percent"], None)
    submission_method = _get_first_attr(opportunity, ["submission_method"], "unknown").lower()
    days_to_deadline = _get_float_attr(opportunity, ["days_to_deadline"], None)

    is_supply_delivery = _get_bool_attr(opportunity, ["is_supply_delivery"], False)
    excluded_by_business_rules = _get_bool_attr(opportunity, ["excluded_by_business_rules"], False)
    briefing_compulsory = _get_bool_attr(opportunity, ["briefing_compulsory"], False)
    auto_quote_triggered = _get_bool_attr(opportunity, ["auto_quote_triggered"], False)
    auto_quote_recommended = _get_bool_attr(opportunity, ["auto_quote_recommended"], False)

    reasons: List[str] = []
    skip_reasons: List[str] = []
    risk_flags: List[str] = []

    if qualification_status in ALLOWED_QUALIFICATION_STATUS:
        reasons.append("Opportunity passed qualification rules")
    else:
        skip_reasons.append("Opportunity is not in qualified status")

    if is_supply_delivery:
        reasons.append("Supply-and-delivery requirement satisfied")
    else:
        skip_reasons.append("Opportunity is not confirmed as supply and delivery")

    if not excluded_by_business_rules:
        reasons.append("No excluded commodity or business-rule block detected")
    else:
        skip_reasons.append("Opportunity is excluded by business rules")

    if not briefing_compulsory:
        reasons.append("No compulsory briefing or site meeting detected")
    else:
        skip_reasons.append("Compulsory briefing or site meeting detected")

    if score_total is not None and score_total >= MIN_SCORE_TO_TRIGGER:
        reasons.append(f"Score threshold met ({score_total:.2f})")
    else:
        skip_reasons.append(
            f"Score below auto-trigger threshold of {MIN_SCORE_TO_TRIGGER:.0f}"
        )

    if estimated_profit_value is not None and estimated_profit_value >= MIN_ESTIMATED_PROFIT:
        reasons.append(
            f"Estimated profit threshold met (R{estimated_profit_value:,.2f})"
        )
    else:
        skip_reasons.append(
            f"Estimated profit below R{MIN_ESTIMATED_PROFIT:,.0f}"
        )

    if assumed_margin_percent is not None and assumed_margin_percent >= MIN_MARGIN_PERCENT:
        reasons.append(f"Margin assumption meets minimum ({assumed_margin_percent:.2f}%)")
    else:
        skip_reasons.append(
            f"Margin assumption below {MIN_MARGIN_PERCENT:.0f}%"
        )

    if submission_method in ALLOWED_SUBMISSION_METHODS:
        reasons.append(f"Submission method is usable ({submission_method})")
    else:
        skip_reasons.append("Submission method is not usable for auto-trigger")

    if days_to_deadline is None:
        skip_reasons.append("Days to deadline is unknown")
    elif days_to_deadline >= (MIN_HOURS_BEFORE_DEADLINE / 24.0):
        reasons.append("Deadline buffer is sufficient for auto-trigger")
    else:
        skip_reasons.append(
            f"Less than {MIN_HOURS_BEFORE_DEADLINE:.0f} hours remain before deadline"
        )

    if auto_quote_triggered:
        skip_reasons.append("Quote was already auto-triggered for this opportunity")

    if auto_quote_recommended:
        reasons.append("Scoring engine recommended auto-quote")
    else:
        risk_flags.append("Scoring engine did not explicitly recommend auto-quote")

    should_trigger = len(skip_reasons) == 0

    return AutoQuoteTriggerResult(
        should_trigger=should_trigger,
        triggered=False,
        skipped=not should_trigger,

        score_total=score_total,
        qualification_status=qualification_status,
        estimated_profit_value=estimated_profit_value,
        assumed_margin_percent=assumed_margin_percent,
        submission_method=submission_method,
        days_to_deadline=days_to_deadline,

        reasons=_dedupe_preserve_order(reasons),
        skip_reasons=_dedupe_preserve_order(skip_reasons),
        risk_flags=_dedupe_preserve_order(risk_flags),

        quote_draft_id=None,
        quote_draft_status=None,
        trigger_source=DEFAULT_TRIGGER_SOURCE,
    )


def create_quote_draft_from_opportunity(db: Any, opportunity: Any) -> Any:
    """
    Create a QuoteDraft from an opportunity.
    Only sets fields that actually exist on the QuoteDraft model.
    """
    quote_draft = QuoteDraft()

    title = _get_first_attr(opportunity, ["title", "name"], "Untitled Opportunity")
    buyer_name = _get_first_attr(opportunity, ["buyer_name", "entity_name", "issuer_name"], "")
    tender_number = _get_first_attr(opportunity, ["tender_number", "reference_number"], "")
    description = _get_first_attr(opportunity, ["description", "summary"], "")
    submission_method = _get_first_attr(opportunity, ["submission_method"], "unknown")
    source_url = _get_first_attr(opportunity, ["source_url", "notice_url"], "")
    value_band = _get_first_attr(opportunity, ["value_band"], "")
    qualification_status = _get_first_attr(opportunity, ["qualification_status"], "")
    score_total = _get_float_attr(opportunity, ["score_total"], None)
    estimated_contract_value = _get_float_attr(
        opportunity,
        ["estimated_contract_value", "estimated_value", "contract_value"],
        None,
    )
    estimated_profit_value = _get_float_attr(opportunity, ["estimated_profit_value"], None)
    opportunity_id = _get_attr(opportunity, "id", None)

    payload = {
        "opportunity_id": opportunity_id,
        "title": title,
        "name": title,
        "draft_name": f"Quote Draft - {title}",
        "opportunity_title": title,
        "buyer_name": buyer_name,
        "entity_name": buyer_name,
        "tender_number": tender_number,
        "reference_number": tender_number,
        "description": description,
        "summary": description[:5000] if description else "",
        "submission_method": submission_method,
        "source_url": source_url,
        "notice_url": source_url,
        "value_band": value_band,
        "qualification_status": qualification_status,
        "trigger_source": DEFAULT_TRIGGER_SOURCE,
        "trigger_score": score_total,
        "draft_status": DEFAULT_DRAFT_STATUS,
        "status": DEFAULT_DRAFT_STATUS,
        "estimated_contract_value": estimated_contract_value,
        "estimated_profit_value": estimated_profit_value,
        "generated_scope_summary": build_scope_summary(opportunity),
        "compliance_status": "pending",
        "quote_generation_status": "queued",
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }

    for field_name, value in payload.items():
        if hasattr(quote_draft, field_name):
            try:
                setattr(quote_draft, field_name, value)
            except Exception as e:
                logger.warning("Could not set QuoteDraft.%s: %s", field_name, e)

    db.add(quote_draft)
    db.commit()
    db.refresh(quote_draft)

    return quote_draft


def enqueue_quote_generation(db: Any, quote_draft: Any) -> Dict[str, Any]:
    """
    Marks the draft as queued and optionally dispatches to Celery if available.
    """
    task_dispatched = False
    task_name = None
    task_error = None

    # Mark queue-related fields if present
    updates = {
        "quote_generation_status": "queued",
        "draft_status": "queued" if hasattr(quote_draft, "draft_status") else None,
        "updated_at": utcnow(),
    }

    for field_name, value in updates.items():
        if value is None:
            continue
        if hasattr(quote_draft, field_name):
            try:
                setattr(quote_draft, field_name, value)
            except Exception as e:
                logger.warning("Could not set %s on QuoteDraft: %s", field_name, e)

    db.add(quote_draft)
    db.commit()
    db.refresh(quote_draft)

    # Try Celery dispatch if the task exists
    try:
        task_module = importlib.import_module("app.tasks.quote_tasks")

        candidate_task_names = [
            "generate_quote_from_draft",
            "generate_quote_draft",
            "run_quote_generation",
        ]

        for name in candidate_task_names:
            task = getattr(task_module, name, None)
            if task is None:
                continue

            task_name = name

            try:
                if hasattr(task, "delay"):
                    task.delay(_get_attr(quote_draft, "id", None))
                else:
                    task(_get_attr(quote_draft, "id", None))
                task_dispatched = True
                break
            except Exception as e:
                task_error = str(e)
                logger.warning("Quote task dispatch failed for %s: %s", name, e)
                break

    except Exception as e:
        task_error = str(e)
        logger.info("Quote task module not available yet: %s", e)

    return {
        "queued": True,
        "task_dispatched": task_dispatched,
        "task_name": task_name,
        "task_error": task_error,
        "quote_draft_id": _get_attr(quote_draft, "id", None),
    }


def auto_trigger_quote_if_qualified(db: Any, opportunity: Any) -> AutoQuoteTriggerResult:
    """
    Full auto-trigger flow:
    1. Decide eligibility
    2. Skip or create QuoteDraft
    3. Queue quote generation
    4. Update opportunity state
    5. Write pipeline event if model exists
    """
    decision = should_trigger_auto_quote(opportunity)

    if not decision.should_trigger:
        apply_trigger_result_to_opportunity(
            opportunity=opportunity,
            result=decision,
            triggered=False,
        )
        db.add(opportunity)
        db.commit()
        db.refresh(opportunity)

        create_pipeline_event(
            db=db,
            opportunity=opportunity,
            event_type="AUTO_QUOTE_SKIPPED",
            status="skipped",
            message="Auto-quote trigger skipped",
            payload=decision.to_dict(),
        )

        return decision

    existing_draft = find_existing_quote_draft_for_opportunity(db=db, opportunity=opportunity)
    if existing_draft is not None:
        result = AutoQuoteTriggerResult(
            should_trigger=False,
            triggered=False,
            skipped=True,

            score_total=decision.score_total,
            qualification_status=decision.qualification_status,
            estimated_profit_value=decision.estimated_profit_value,
            assumed_margin_percent=decision.assumed_margin_percent,
            submission_method=decision.submission_method,
            days_to_deadline=decision.days_to_deadline,

            reasons=decision.reasons,
            skip_reasons=["QuoteDraft already exists for this opportunity"],
            risk_flags=decision.risk_flags,

            quote_draft_id=_get_attr(existing_draft, "id", None),
            quote_draft_status=_get_first_attr(existing_draft, ["draft_status", "status"], ""),
            trigger_source=DEFAULT_TRIGGER_SOURCE,
        )

        apply_trigger_result_to_opportunity(
            opportunity=opportunity,
            result=result,
            triggered=False,
        )
        db.add(opportunity)
        db.commit()
        db.refresh(opportunity)

        create_pipeline_event(
            db=db,
            opportunity=opportunity,
            event_type="AUTO_QUOTE_SKIPPED",
            status="duplicate",
            message="QuoteDraft already exists",
            payload=result.to_dict(),
        )

        return result

    quote_draft = create_quote_draft_from_opportunity(db=db, opportunity=opportunity)
    queue_result = enqueue_quote_generation(db=db, quote_draft=quote_draft)

    result = AutoQuoteTriggerResult(
        should_trigger=True,
        triggered=True,
        skipped=False,

        score_total=decision.score_total,
        qualification_status=decision.qualification_status,
        estimated_profit_value=decision.estimated_profit_value,
        assumed_margin_percent=decision.assumed_margin_percent,
        submission_method=decision.submission_method,
        days_to_deadline=decision.days_to_deadline,

        reasons=decision.reasons + ["QuoteDraft created and queued"],
        skip_reasons=[],
        risk_flags=decision.risk_flags,

        quote_draft_id=_get_attr(quote_draft, "id", None),
        quote_draft_status=_get_first_attr(quote_draft, ["draft_status", "status"], DEFAULT_DRAFT_STATUS),
        trigger_source=DEFAULT_TRIGGER_SOURCE,
    )

    apply_trigger_result_to_opportunity(
        opportunity=opportunity,
        result=result,
        triggered=True,
    )
    db.add(opportunity)
    db.commit()
    db.refresh(opportunity)

    create_pipeline_event(
        db=db,
        opportunity=opportunity,
        event_type="AUTO_QUOTE_TRIGGERED",
        status="success",
        message="Auto-quote triggered successfully",
        payload={
            "trigger_result": result.to_dict(),
            "queue_result": queue_result,
        },
    )

    return result


# =========================================================
# Opportunity / draft helpers
# =========================================================
def find_existing_quote_draft_for_opportunity(db: Any, opportunity: Any) -> Optional[Any]:
    opportunity_id = _get_attr(opportunity, "id", None)
    if opportunity_id is None:
        return None

    query = db.query(QuoteDraft)

    if hasattr(QuoteDraft, "opportunity_id"):
        found = query.filter(QuoteDraft.opportunity_id == opportunity_id).first()
        if found:
            return found

    title = _get_first_attr(opportunity, ["title", "name"], "")
    tender_number = _get_first_attr(opportunity, ["tender_number", "reference_number"], "")

    candidates = query.limit(500).all()
    for row in candidates:
        row_title = _get_first_attr(row, ["title", "name", "opportunity_title"], "")
        row_tender = _get_first_attr(row, ["tender_number", "reference_number"], "")

        if tender_number and _norm_eq(row_tender, tender_number):
            return row
        if title and _norm_eq(row_title, title):
            return row

    return None


def apply_trigger_result_to_opportunity(
    opportunity: Any,
    result: AutoQuoteTriggerResult,
    triggered: bool,
) -> Any:
    field_values = {
        "auto_quote_triggered": triggered,
        "auto_quote_triggered_at": utcnow() if triggered else None,
        "auto_quote_trigger_result_json": result.to_dict(),
        "auto_quote_trigger_reason": "; ".join(result.reasons if triggered else result.skip_reasons)[:4000],
        "quote_draft_id": result.quote_draft_id,
        "pipeline_stage": "quote_triggered" if triggered else "quote_trigger_skipped",
        "updated_at": utcnow(),
    }

    for field_name, value in field_values.items():
        if value is None and field_name != "auto_quote_triggered_at":
            continue
        if hasattr(opportunity, field_name):
            try:
                setattr(opportunity, field_name, value)
            except Exception as e:
                logger.warning("Could not set %s on opportunity: %s", field_name, e)

    return opportunity


def build_scope_summary(opportunity: Any) -> str:
    title = _get_first_attr(opportunity, ["title", "name"], "")
    buyer_name = _get_first_attr(opportunity, ["buyer_name", "entity_name", "issuer_name"], "")
    tender_number = _get_first_attr(opportunity, ["tender_number", "reference_number"], "")
    province = _get_first_attr(opportunity, ["province"], "")
    submission_method = _get_first_attr(opportunity, ["submission_method"], "")
    estimated_contract_value = _get_float_attr(
        opportunity,
        ["estimated_contract_value", "estimated_value", "contract_value"],
        None,
    )
    estimated_profit_value = _get_float_attr(opportunity, ["estimated_profit_value"], None)

    parts = [
        f"Opportunity: {title}" if title else "",
        f"Buyer: {buyer_name}" if buyer_name else "",
        f"Tender number: {tender_number}" if tender_number else "",
        f"Province: {province}" if province else "",
        f"Submission method: {submission_method}" if submission_method else "",
        f"Estimated contract value: R{estimated_contract_value:,.2f}" if estimated_contract_value is not None else "",
        f"Estimated profit: R{estimated_profit_value:,.2f}" if estimated_profit_value is not None else "",
    ]
    return "\n".join([p for p in parts if p]).strip()


# =========================================================
# Pipeline event helper
# =========================================================
def create_pipeline_event(
    db: Any,
    opportunity: Any,
    event_type: str,
    status: str,
    message: str,
    payload: Dict[str, Any],
) -> None:
    if TenderPipelineEvent is None:
        return

    try:
        event = TenderPipelineEvent()
        event_data = {
            "opportunity_id": _get_attr(opportunity, "id", None),
            "event_type": event_type,
            "status": status,
            "message": message,
            "payload_json": payload,
            "created_at": utcnow(),
        }

        for field_name, value in event_data.items():
            if hasattr(event, field_name):
                setattr(event, field_name, value)

        db.add(event)
        db.commit()
    except Exception as e:
        logger.warning("Could not create pipeline event: %s", e)
        try:
            db.rollback()
        except Exception:
            pass


# =========================================================
# Utilities
# =========================================================
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_attr(obj: Any, field_name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, field_name, default)
    except Exception:
        return default


def _get_first_attr(obj: Any, field_names: List[str], default: str = "") -> str:
    for field_name in field_names:
        try:
            value = getattr(obj, field_name, None)
            if value is None:
                continue
            s = str(value).strip()
            if s:
                return s
        except Exception:
            continue
    return default


def _get_float_attr(obj: Any, field_names: List[str], default: Optional[float] = None) -> Optional[float]:
    for field_name in field_names:
        try:
            value = getattr(obj, field_name, None)
            converted = _to_float(value)
            if converted is not None:
                return converted
        except Exception:
            continue
    return default


def _get_bool_attr(obj: Any, field_names: List[str], default: bool = False) -> bool:
    for field_name in field_names:
        try:
            value = getattr(obj, field_name, None)
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                value_norm = value.strip().lower()
                if value_norm in {"true", "1", "yes", "y"}:
                    return True
                if value_norm in {"false", "0", "no", "n"}:
                    return False
            if isinstance(value, (int, float)):
                return bool(value)
        except Exception:
            continue
    return default


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    if not s:
        return None

    s = s.replace("R", "").replace("ZAR", "").replace(" ", "")

    if s.count(",") > 0 and s.count(".") > 0:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        s = s.replace(",", "")

    try:
        return float(s)
    except Exception:
        return None


def _norm_eq(a: Any, b: Any) -> bool:
    return _normalize_text(str(a or "")) == _normalize_text(str(b or ""))


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for v in values:
        key = v.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out
