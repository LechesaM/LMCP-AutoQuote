from __future__ import annotations

import re
from typing import Any, Dict, List


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _collect_text(payload: Dict[str, Any]) -> str:
    parts = [
        payload.get("tender_id"),
        payload.get("title"),
        payload.get("buyer_name"),
        payload.get("category"),
        payload.get("description"),
        payload.get("submission_instructions"),
        payload.get("extracted_text"),
        payload.get("source_text"),
    ]
    for key in ("documents", "line_items"):
        for item in payload.get(key) or []:
            if isinstance(item, dict):
                parts.extend([item.get("name"), item.get("description"), item.get("notes"), item.get("extracted_text")])
    return _normalize(" ".join(str(part or "") for part in parts))


PATTERNS: List[Dict[str, Any]] = [
    {
        "name": "compulsory_briefing_session",
        "regexes": [r"compulsory briefing", r"mandatory briefing", r"mandatory site meeting", r"attendance is compulsory", r"briefing compulsory"],
        "risk_flags": ["briefing_compulsory"],
        "manual_review_triggers": ["compulsory briefing session"],
        "disqualification_triggers": [],
    },
    {
        "name": "non_compulsory_briefing",
        "regexes": [r"optional briefing", r"non-compulsory briefing", r"briefing is optional", r"optional site meeting"],
        "risk_flags": ["briefing_optional"],
        "manual_review_triggers": [],
        "disqualification_triggers": [],
    },
    {
        "name": "mandatory_site_inspection",
        "regexes": [r"mandatory site inspection", r"compulsory site inspection", r"site inspection compulsory", r"mandatory site meeting", r"site visit compulsory"],
        "risk_flags": ["site_inspection_required"],
        "manual_review_triggers": ["mandatory site inspection"],
        "disqualification_triggers": [],
    },
    {
        "name": "functionality_scoring",
        "regexes": [r"functionality scoring", r"functionality points", r"technical functionality", r"technical score", r"minimum functionality"],
        "risk_flags": ["functionality_scoring"],
        "manual_review_triggers": ["functionality scoring"],
        "disqualification_triggers": [],
    },
    {
        "name": "minimum_functionality_threshold",
        "regexes": [r"minimum functionality threshold", r"threshold of \d+", r"must achieve \d+%?", r"minimum score of \d+"],
        "risk_flags": ["minimum_functionality_threshold"],
        "manual_review_triggers": ["minimum functionality threshold"],
        "disqualification_triggers": [],
    },
    {
        "name": "cidb_requirement",
        "regexes": [r"\bcidb\b", r"cidb registration", r"cidb grading"],
        "risk_flags": ["cidb_requirement"],
        "manual_review_triggers": ["CIDB requirement"],
        "disqualification_triggers": [],
    },
    {
        "name": "local_content_requirement",
        "regexes": [r"local content", r"designated sector", r"local production"],
        "risk_flags": ["local_content_requirement"],
        "manual_review_triggers": ["local content requirement"],
        "disqualification_triggers": [],
    },
    {
        "name": "subcontracting_requirement",
        "regexes": [r"subcontracting", r"sub-contracting", r"joint venture", r"consortium"],
        "risk_flags": ["subcontracting_requirement"],
        "manual_review_triggers": ["subcontracting requirement"],
        "disqualification_triggers": [],
    },
    {
        "name": "oem_or_accreditation_requirement",
        "regexes": [r"\boem\b", r"oem accreditation", r"manufacturer accreditation", r"accreditation certificate", r"certified installer"],
        "risk_flags": ["oem_accreditation_requirement"],
        "manual_review_triggers": ["OEM or accreditation requirement"],
        "disqualification_triggers": [],
    },
    {
        "name": "sample_requirement",
        "regexes": [r"sample required", r"samples required", r"provide sample", r"submission of sample", r"demo sample"],
        "risk_flags": ["sample_requirement"],
        "manual_review_triggers": ["sample requirement"],
        "disqualification_triggers": [],
    },
    {
        "name": "warranty_requirement",
        "regexes": [r"warranty", r"guarantee period", r"warranted for", r"extended warranty"],
        "risk_flags": ["warranty_requirement"],
        "manual_review_triggers": ["warranty requirement"],
        "disqualification_triggers": [],
    },
    {
        "name": "delivery_deadline",
        "regexes": [r"delivery within", r"delivery deadline", r"deliver by", r"within \d+ days", r"lead time"],
        "risk_flags": ["delivery_deadline"],
        "manual_review_triggers": ["delivery deadline"],
        "disqualification_triggers": [],
    },
    {
        "name": "contract_duration",
        "regexes": [r"contract duration", r"for \d+ months", r"for \d+ years", r"period of \d+"],
        "risk_flags": ["contract_duration"],
        "manual_review_triggers": [],
        "disqualification_triggers": [],
    },
    {
        "name": "disqualification_clauses",
        "regexes": [r"failure to.*disqualif", r"non-compliance will result in disqualification", r"late submissions will not be accepted", r"disqualified if", r"will be disqualified"],
        "risk_flags": ["disqualification_clause"],
        "manual_review_triggers": ["disqualification clause"],
        "disqualification_triggers": ["disqualification clause"],
    },
    {
        "name": "late_submission_clauses",
        "regexes": [r"late submissions will not be accepted", r"no late submissions", r"late bids will be rejected", r"after closing time will not be considered"],
        "risk_flags": ["late_submission_clause"],
        "manual_review_triggers": ["late submission clause"],
        "disqualification_triggers": ["late submission clause"],
    },
    {
        "name": "pricing_schedule_requirement",
        "regexes": [r"pricing schedule", r"price schedule", r"schedule of rates"],
        "risk_flags": ["pricing_schedule_requirement"],
        "manual_review_triggers": [],
        "disqualification_triggers": [],
    },
    {
        "name": "company_letterhead_requirement",
        "regexes": [r"company letterhead", r"quotation on company letterhead", r"letterhead quotation"],
        "risk_flags": ["company_letterhead_requirement"],
        "manual_review_triggers": [],
        "disqualification_triggers": [],
    },
    {
        "name": "e_submission_requirement",
        "regexes": [r"e-submission", r"e tender", r"e-tender", r"electronic submission", r"online submission", r"portal submission"],
        "risk_flags": ["e_submission_requirement"],
        "manual_review_triggers": [],
        "disqualification_triggers": [],
    },
    {
        "name": "email_submission_requirement",
        "regexes": [r"submit by email", r"email submission", r"email to", r"e-mail submission", r"submitted via email"],
        "risk_flags": ["email_submission_requirement"],
        "manual_review_triggers": [],
        "disqualification_triggers": [],
    },
    {
        "name": "physical_submission_requirement",
        "regexes": [r"physical delivery", r"hand delivery", r"courier", r"tender box", r"dropbox", r"drop box"],
        "risk_flags": ["physical_submission_requirement"],
        "manual_review_triggers": ["physical submission requirement"],
        "disqualification_triggers": [],
    },
]


def analyze_rfq_language(rfq_record_or_dict: Any) -> Dict[str, Any]:
    if isinstance(rfq_record_or_dict, str):
        payload = {"extracted_text": rfq_record_or_dict}
    else:
        payload = dict(rfq_record_or_dict or {})
    text = _collect_text(payload)
    detected_patterns: List[Dict[str, Any]] = []
    risk_flags: List[str] = []
    manual_review_triggers: List[str] = []
    disqualification_triggers: List[str] = []
    evidence_phrases: List[str] = []

    for pattern in PATTERNS:
        matches: List[str] = []
        for regex in pattern["regexes"]:
            found = re.findall(regex, text)
            if found:
                matches.extend([str(item) for item in found if str(item).strip()])
        if not matches:
            continue
        evidence = list(dict.fromkeys(matches))
        detected_patterns.append(
            {
                "name": pattern["name"],
                "confidence": round(min(0.99, 0.75 + (0.04 * len(evidence))), 2),
                "evidence_phrases": evidence[:5],
            }
        )
        evidence_phrases.extend(evidence)
        risk_flags.extend(pattern["risk_flags"])
        manual_review_triggers.extend(pattern["manual_review_triggers"])
        disqualification_triggers.extend(pattern["disqualification_triggers"])

    if re.search(r"functionality.*threshold|threshold.*functionality|minimum functionality", text):
        manual_review_triggers.append("functionality threshold")
        risk_flags.append("functionality_threshold")
    if re.search(r"late submission|late bids|after closing time", text):
        risk_flags.append("late_submission_risk")
    if re.search(r"sample required|samples required|provide sample", text):
        manual_review_triggers.append("sample requirement")
    if re.search(r"oem|accreditation", text):
        manual_review_triggers.append("OEM or accreditation requirement")

    confidence = round(min(0.99, 0.45 + 0.08 * len(detected_patterns)), 2)
    return {
        "text": text,
        "detected_patterns": detected_patterns,
        "risk_flags": list(dict.fromkeys(risk_flags)),
        "manual_review_triggers": list(dict.fromkeys(manual_review_triggers)),
        "disqualification_triggers": list(dict.fromkeys(disqualification_triggers)),
        "confidence": confidence,
        "evidence_phrases": list(dict.fromkeys(evidence_phrases)),
    }


def summarize_language_intelligence(language_report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "pattern_count": len(language_report.get("detected_patterns", [])),
        "risk_flag_count": len(language_report.get("risk_flags", [])),
        "manual_review_trigger_count": len(language_report.get("manual_review_triggers", [])),
        "disqualification_trigger_count": len(language_report.get("disqualification_triggers", [])),
        "confidence": float(language_report.get("confidence", 0.0)),
    }
