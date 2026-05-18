from __future__ import annotations

from typing import List, Optional

from app.services.tender_pipeline_models import (
    BriefingRequirement,
    EligibilityDecision,
    EligibilityResult,
    NormalizedTender,
    SubmissionMethod,
    TenderStatus,
)


DEFAULT_ALLOWED_SUBMISSION_METHODS = {
    SubmissionMethod.EMAIL,
    SubmissionMethod.PORTAL,
}

DEFAULT_REJECTED_SUBMISSION_METHODS = {
    SubmissionMethod.PHYSICAL,
    SubmissionMethod.COURIER,
}


class TenderEligibilityEngine:
    """
    Enforces LMCP tender pursuit rules.

    Core business rules:
    - Allow EMAIL-only submissions
    - Allow PORTAL-only submissions
    - Reject compulsory briefing tenders
    - Reject physical/courier-only tenders
    - Send unclear tenders to manual review
    """

    def __init__(
        self,
        *,
        require_deadline: bool = True,
        require_issuing_entity: bool = True,
        require_title: bool = True,
        require_contact_for_email: bool = True,
        allow_manual_review_for_unknowns: bool = True,
    ) -> None:
        self.require_deadline = require_deadline
        self.require_issuing_entity = require_issuing_entity
        self.require_title = require_title
        self.require_contact_for_email = require_contact_for_email
        self.allow_manual_review_for_unknowns = allow_manual_review_for_unknowns

    def evaluate(self, tender: NormalizedTender) -> EligibilityResult:
        reasons: List[str] = []
        passed_checks: List[str] = []
        failed_checks: List[str] = []

        hard_reject = False
        manual_review = False

        # ------------------------------------------------------------------
        # 1. Basic structural checks
        # ------------------------------------------------------------------
        if self.require_title:
            if tender.title and tender.title.strip():
                passed_checks.append("Tender title is present.")
            else:
                failed_checks.append("Tender title is missing.")
                reasons.append("Missing tender title.")
                manual_review = True

        if self.require_issuing_entity:
            if tender.issuing_entity and tender.issuing_entity.strip():
                passed_checks.append("Issuing entity is present.")
            else:
                failed_checks.append("Issuing entity is missing.")
                reasons.append("Missing issuing entity.")
                manual_review = True

        if self.require_deadline:
            if tender.closing_at is not None:
                passed_checks.append("Closing date was found.")
            else:
                failed_checks.append("Closing date is missing.")
                reasons.append("Missing closing date.")
                manual_review = True

        # ------------------------------------------------------------------
        # 2. Submission rules
        # ------------------------------------------------------------------
        submission_result = self._evaluate_submission_method(tender)
        reasons.extend(submission_result["reasons"])
        passed_checks.extend(submission_result["passed_checks"])
        failed_checks.extend(submission_result["failed_checks"])
        hard_reject = hard_reject or submission_result["hard_reject"]
        manual_review = manual_review or submission_result["manual_review"]

        # ------------------------------------------------------------------
        # 3. Briefing rules
        # ------------------------------------------------------------------
        briefing_result = self._evaluate_briefing(tender)
        reasons.extend(briefing_result["reasons"])
        passed_checks.extend(briefing_result["passed_checks"])
        failed_checks.extend(briefing_result["failed_checks"])
        hard_reject = hard_reject or briefing_result["hard_reject"]
        manual_review = manual_review or briefing_result["manual_review"]

        # ------------------------------------------------------------------
        # 4. Contact / operational checks
        # ------------------------------------------------------------------
        contact_result = self._evaluate_contact_requirements(tender)
        reasons.extend(contact_result["reasons"])
        passed_checks.extend(contact_result["passed_checks"])
        failed_checks.extend(contact_result["failed_checks"])
        hard_reject = hard_reject or contact_result["hard_reject"]
        manual_review = manual_review or contact_result["manual_review"]

        # ------------------------------------------------------------------
        # 5. Build final decision
        # ------------------------------------------------------------------
        if hard_reject:
            decision = EligibilityDecision.INELIGIBLE
        elif manual_review:
            decision = (
                EligibilityDecision.MANUAL_REVIEW
                if self.allow_manual_review_for_unknowns
                else EligibilityDecision.INELIGIBLE
            )
            if not self.allow_manual_review_for_unknowns:
                reasons.append("Manual review is disabled; unclear tender marked ineligible.")
        else:
            decision = EligibilityDecision.ELIGIBLE
            reasons.append("Tender satisfies LMCP automatic pursuit rules.")

        result = EligibilityResult(
            decision=decision,
            reasons=self._deduplicate(reasons),
            passed_checks=self._deduplicate(passed_checks),
            failed_checks=self._deduplicate(failed_checks),
        )

        self._apply_result_to_tender(tender, result)
        return result

    def _evaluate_submission_method(self, tender: NormalizedTender) -> dict:
        reasons: List[str] = []
        passed_checks: List[str] = []
        failed_checks: List[str] = []

        hard_reject = False
        manual_review = False

        method = tender.submission_method

        if method in DEFAULT_REJECTED_SUBMISSION_METHODS:
            failed_checks.append(
                f"Submission method '{method.value}' is not allowed by LMCP rules."
            )
            reasons.append(
                f"Tender requires {method.value} submission, which is outside LMCP target workflow."
            )
            hard_reject = True
            return self._response_dict(
                reasons, passed_checks, failed_checks, hard_reject, manual_review
            )

        if method == SubmissionMethod.UNKNOWN:
            failed_checks.append("Submission method could not be determined.")
            reasons.append("Submission method is unclear.")
            manual_review = True
            return self._response_dict(
                reasons, passed_checks, failed_checks, hard_reject, manual_review
            )

        # Preferred cases
        if tender.is_email_only:
            passed_checks.append("Tender is email-only.")
            reasons.append("Email-only submission is allowed.")
        elif tender.is_portal_only:
            passed_checks.append("Tender is portal-only.")
            reasons.append("Portal-only submission is allowed.")
        else:
            # Mixed or ambiguous cases
            if method == SubmissionMethod.EMAIL:
                passed_checks.append("Tender allows email submission.")
                if tender.flags.physical_submission_required or tender.flags.courier_submission_required:
                    failed_checks.append("Tender also appears to require physical/courier submission.")
                    reasons.append("Email submission exists but additional disallowed submission requirements were detected.")
                    hard_reject = True
                else:
                    reasons.append("Tender allows email submission but is not confirmed email-only.")
                    manual_review = True

            elif method == SubmissionMethod.PORTAL:
                passed_checks.append("Tender allows portal submission.")
                if tender.flags.physical_submission_required or tender.flags.courier_submission_required:
                    failed_checks.append("Tender also appears to require physical/courier submission.")
                    reasons.append("Portal submission exists but additional disallowed submission requirements were detected.")
                    hard_reject = True
                else:
                    reasons.append("Tender allows portal submission but is not confirmed portal-only.")
                    manual_review = True

            else:
                failed_checks.append(f"Unhandled submission method '{method.value}'.")
                reasons.append("Submission method needs manual verification.")
                manual_review = True

        # Extra email checks
        if method == SubmissionMethod.EMAIL:
            if tender.submission_email:
                passed_checks.append("Submission email address is present.")
            else:
                failed_checks.append("Submission email address is missing.")
                reasons.append("Email submission was detected but no submission email address was extracted.")
                manual_review = True

        # Extra portal checks
        if method == SubmissionMethod.PORTAL:
            if tender.portal_url or tender.portal_name or tender.source_url:
                passed_checks.append("Portal submission details are present.")
            else:
                failed_checks.append("Portal submission details are missing.")
                reasons.append("Portal submission was detected but no portal details were extracted.")
                manual_review = True

        return self._response_dict(
            reasons, passed_checks, failed_checks, hard_reject, manual_review
        )

    def _evaluate_briefing(self, tender: NormalizedTender) -> dict:
        reasons: List[str] = []
        passed_checks: List[str] = []
        failed_checks: List[str] = []

        hard_reject = False
        manual_review = False

        if tender.briefing_requirement == BriefingRequirement.COMPULSORY:
            failed_checks.append("Compulsory briefing was detected.")
            reasons.append("Tender has a compulsory briefing and must be rejected.")
            hard_reject = True
        elif tender.briefing_requirement == BriefingRequirement.NONE:
            passed_checks.append("No briefing requirement detected.")
            reasons.append("No briefing requirement was found.")
        elif tender.briefing_requirement == BriefingRequirement.OPTIONAL:
            passed_checks.append("Optional briefing detected.")
            reasons.append("Optional briefing is acceptable.")
        else:
            failed_checks.append("Briefing requirement is unclear.")
            reasons.append("Briefing requirement could not be confirmed.")
            manual_review = True

        return self._response_dict(
            reasons, passed_checks, failed_checks, hard_reject, manual_review
        )

    def _evaluate_contact_requirements(self, tender: NormalizedTender) -> dict:
        reasons: List[str] = []
        passed_checks: List[str] = []
        failed_checks: List[str] = []

        hard_reject = False
        manual_review = False

        if tender.contact_details:
            passed_checks.append("Contact details were extracted.")
        else:
            failed_checks.append("No contact details were extracted.")
            reasons.append("No contact details found in tender.")
            manual_review = True

        if tender.submission_method == SubmissionMethod.EMAIL and self.require_contact_for_email:
            if tender.submission_email:
                passed_checks.append("Email submission destination is available.")
            else:
                failed_checks.append("No submission email address is available for an email tender.")
                reasons.append("Email tender cannot be pursued automatically without a submission email address.")
                manual_review = True

        if tender.flags.deadline_found:
            passed_checks.append("Tender deadline exists.")
        else:
            failed_checks.append("Tender deadline is missing.")
            reasons.append("Tender deadline is missing.")
            manual_review = True

        return self._response_dict(
            reasons, passed_checks, failed_checks, hard_reject, manual_review
        )

    def _apply_result_to_tender(
        self,
        tender: NormalizedTender,
        result: EligibilityResult,
    ) -> None:
        tender.eligibility = result

        if result.decision == EligibilityDecision.ELIGIBLE:
            tender.status = TenderStatus.ELIGIBLE
            tender.flags.requires_manual_review = False
            tender.add_tag("eligible")
            tender.add_note("Tender passed automatic eligibility screening.")
        elif result.decision == EligibilityDecision.INELIGIBLE:
            tender.status = TenderStatus.INELIGIBLE
            tender.flags.requires_manual_review = False
            tender.add_tag("ineligible")
            tender.add_note("Tender failed automatic eligibility screening.")
        else:
            tender.status = TenderStatus.MANUAL_REVIEW
            tender.flags.requires_manual_review = True
            tender.add_tag("manual_review")
            tender.add_note("Tender requires manual review before pursuit.")

    @staticmethod
    def _response_dict(
        reasons: List[str],
        passed_checks: List[str],
        failed_checks: List[str],
        hard_reject: bool,
        manual_review: bool,
    ) -> dict:
        return {
            "reasons": reasons,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "hard_reject": hard_reject,
            "manual_review": manual_review,
        }

    @staticmethod
    def _deduplicate(items: List[str]) -> List[str]:
        seen = set()
        result: List[str] = []
        for item in items:
            clean = item.strip()
            if clean and clean not in seen:
                seen.add(clean)
                result.append(clean)
        return result


def evaluate_tender_eligibility(
    tender: NormalizedTender,
    *,
    require_deadline: bool = True,
    require_issuing_entity: bool = True,
    require_title: bool = True,
    require_contact_for_email: bool = True,
    allow_manual_review_for_unknowns: bool = True,
) -> EligibilityResult:
    """
    Convenience function for one-shot eligibility checks.
    """
    engine = TenderEligibilityEngine(
        require_deadline=require_deadline,
        require_issuing_entity=require_issuing_entity,
        require_title=require_title,
        require_contact_for_email=require_contact_for_email,
        allow_manual_review_for_unknowns=allow_manual_review_for_unknowns,
    )
    return engine.evaluate(tender)


def is_tender_eligible(tender: NormalizedTender) -> bool:
    """
    Lightweight helper that evaluates and returns only a boolean.
    """
    result = evaluate_tender_eligibility(tender)
    return result.decision == EligibilityDecision.ELIGIBLE


def summarize_eligibility(tender: NormalizedTender) -> dict:
    """
    Useful for API responses and dashboard cards.
    """
    result: Optional[EligibilityResult] = tender.eligibility

    return {
        "tender_id": tender.tender_id,
        "title": tender.title,
        "issuing_entity": tender.issuing_entity,
        "submission_method": tender.submission_method.value,
        "briefing_requirement": tender.briefing_requirement.value,
        "decision": result.decision.value if result else None,
        "status": tender.status.value,
        "requires_manual_review": tender.flags.requires_manual_review,
        "reasons": result.reasons if result else [],
        "passed_checks": result.passed_checks if result else [],
        "failed_checks": result.failed_checks if result else [],
    }
