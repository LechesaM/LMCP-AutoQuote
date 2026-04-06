from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List


def _clean(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _extract_buyer_name(opportunity: Dict[str, Any]) -> str:
    return _clean(opportunity.get("buyer_name")) or "Procurement Office"


def _extract_reference(opportunity: Dict[str, Any]) -> str:
    return (
        _clean(opportunity.get("tender_id"))
        or _clean(opportunity.get("ocid"))
        or "N/A"
    )


def _extract_title(opportunity: Dict[str, Any]) -> str:
    return _clean(opportunity.get("title"), "Untitled Opportunity")


def _extract_description(opportunity: Dict[str, Any]) -> str:
    return _clean(opportunity.get("description"))


def _extract_closing_date(opportunity: Dict[str, Any]) -> str:
    return _clean(opportunity.get("tender_period_end")) or "Not stated"


def _infer_delivery_period(opportunity: Dict[str, Any]) -> str:
    title = _extract_title(opportunity).lower()
    description = _extract_description(opportunity).lower()
    text = f"{title} {description}"

    if "urgent" in text:
        return "Immediate to 7 working days from receipt of official purchase order, subject to stock availability."
    if "offload" in text:
        return "7 to 14 working days from receipt of official purchase order, including delivery and offloading where required."
    return "14 to 21 working days from receipt of official purchase order, subject to stock availability."


def _infer_validity_period() -> str:
    return "This quotation shall remain valid for 14 calendar days from date of issue."


def _infer_exclusions() -> List[str]:
    return [
        "Any goods, services, or deliverables not expressly described in the RFQ documents.",
        "Offloading equipment unless specifically required in the RFQ.",
        "Storage costs resulting from delayed acceptance by the client.",
        "Escalations caused by supplier price changes after quotation validity expiry.",
        "Any site-specific installation or commissioning unless expressly included in the RFQ.",
    ]


def _infer_assumptions() -> List[str]:
    return [
        "Pricing will be based on current supplier quotations and market availability.",
        "The client will provide complete RFQ documentation, specifications, and delivery details.",
        "Equivalent approved brands may be proposed where permitted by the RFQ.",
        "Delivery access and receiving arrangements will be confirmed before dispatch.",
    ]


def _infer_risk_flags(opportunity: Dict[str, Any]) -> List[str]:
    title = _extract_title(opportunity).lower()
    description = _extract_description(opportunity).lower()
    text = f"{title} {description}"

    risks: List[str] = []

    if "mandatory briefing" in text or "compulsory briefing" in text:
        risks.append("Mandatory briefing session may be required.")
    if "local content" in text:
        risks.append("Local content requirements may apply.")
    if "sample" in text:
        risks.append("Product samples may be required.")
    if "sans" in text or "sabs" in text:
        risks.append("Technical standards compliance may be required.")
    if "urgent" in text:
        risks.append("Urgent delivery requirements may affect supplier pricing and stock.")
    if not risks:
        risks.append("Manual compliance review required before final submission.")

    return risks


def build_scope_summary(opportunity: Dict[str, Any]) -> str:
    title = _extract_title(opportunity)
    description = _extract_description(opportunity)

    if description:
        return (
            f"Lechesa Manaba Consulting and Projects (Pty) Ltd intends to submit a quotation for "
            f"'{title}'. Based on the published information, the requirement appears to involve: "
            f"{description}"
        )

    return (
        f"Lechesa Manaba Consulting and Projects (Pty) Ltd intends to submit a quotation for "
        f"'{title}'. The final scope will be aligned with the official RFQ documents and specifications."
    )


def build_cover_letter(opportunity: Dict[str, Any]) -> str:
    buyer_name = _extract_buyer_name(opportunity)
    reference = _extract_reference(opportunity)
    title = _extract_title(opportunity)

    return f"""To: {buyer_name}

Dear Sir / Madam

QUOTATION SUBMISSION: {title}
RFQ / TENDER REFERENCE: {reference}

Lechesa Manaba Consulting and Projects (Pty) Ltd hereby confirms its intention to submit a quotation for the above-mentioned requirement.

We confirm that we are able to supply and deliver the requested goods subject to final verification of the RFQ documents, technical specifications, delivery conditions, and commercial requirements.

Our company remains committed to quality supply, compliant materials, timely delivery, and professional contract administration.

Yours faithfully

Lechesa Manaba
Director
Lechesa Manaba Consulting and Projects (Pty) Ltd
""".strip()


def build_pricing_notes(opportunity: Dict[str, Any]) -> str:
    assumptions_block = "\n".join(f"- {item}" for item in _infer_assumptions())
    exclusions_block = "\n".join(f"- {item}" for item in _infer_exclusions())

    return f"""PRICING ASSUMPTIONS
{assumptions_block}

EXCLUSIONS
{exclusions_block}
""".strip()


def build_internal_review_notes(opportunity: Dict[str, Any]) -> str:
    risks_block = "\n".join(f"- {item}" for item in _infer_risk_flags(opportunity))

    return f"""INTERNAL REVIEW NOTES
- Confirm submission method.
- Confirm closing date and time.
- Confirm mandatory returnable documents.
- Confirm tax compliance, CSD, and company registration documents.
- Confirm whether pricing must include delivery, offloading, installation, or commissioning.
- Confirm delivery address and lead time.

RISK FLAGS
{risks_block}
""".strip()


def build_quote_draft(opportunity: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.utcnow()

    return {
        "buyer_name": _extract_buyer_name(opportunity),
        "reference_number": _extract_reference(opportunity),
        "title": _extract_title(opportunity),
        "description": _extract_description(opportunity),
        "category": "Supply and Delivery",
        "closing_date": _extract_closing_date(opportunity),
        "delivery_period": _infer_delivery_period(opportunity),
        "validity_period": _infer_validity_period(),
        "scope_summary": build_scope_summary(opportunity),
        "cover_letter": build_cover_letter(opportunity),
        "pricing_notes": build_pricing_notes(opportunity),
        "internal_review_notes": build_internal_review_notes(opportunity),
        "status": "draft",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(days=14)).isoformat(),
    }
