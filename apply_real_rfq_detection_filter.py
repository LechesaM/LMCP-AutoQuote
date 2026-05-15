from pathlib import Path
from datetime import datetime

TARGET = Path("app/services/safe_autonomous_scheduler_service.py")

NEW_HELPER = '''
RFQ_EVIDENCE_PATTERNS = [
    r"\\brfq[\\s:/#_-]*[a-z0-9][a-z0-9/_-]{2,}",
    r"\\brfp[\\s:/#_-]*[a-z0-9][a-z0-9/_-]{2,}",
    r"\\brfx[\\s:/#_-]*[a-z0-9][a-z0-9/_-]{2,}",
    r"\\btender[\\s:/#_-]*[a-z0-9][a-z0-9/_-]{2,}",
    r"\\bquotation[\\s:/#_-]*[a-z0-9][a-z0-9/_-]{2,}",
    r"\\bbid[\\s:/#_-]*[a-z0-9][a-z0-9/_-]{2,}",
]

LISTING_PAGE_KEYWORDS = [
    "latest tenders",
    "current tenders",
    "tenders archive",
    "view latest tenders",
    "rfp & rfq procurement",
    "rfq/tenders",
    "tender opportunities",
    "procurement portal",
    "tenders |",
    "tenders -",
]


def _has_real_rfq_evidence(tender: Dict[str, Any]) -> Dict[str, Any]:
    blob = " ".join(
        str(tender.get(k) or "")
        for k in [
            "buyer_rfq_number",
            "rfq_number",
            "reference_number",
            "document_number",
            "tender_number",
            "title",
            "description",
            "raw_text",
            "submission_message",
            "submission_method",
            "closing_date",
            "closing_datetime",
            "deadline",
            "document_url",
            "detail_url",
            "source_url",
        ]
    ).lower()

    listing_hits = [kw for kw in LISTING_PAGE_KEYWORDS if kw in blob]

    pattern_hits = []
    for pattern in RFQ_EVIDENCE_PATTERNS:
        try:
            if re.search(pattern, blob, flags=re.IGNORECASE):
                pattern_hits.append(pattern)
        except Exception:
            pass

    has_closing = any(token in blob for token in ["closing date", "closing:", "deadline", "closing_datetime", "closing at"])
    has_submission = any(token in blob for token in ["submit", "submission", "email", "portal", "hand delivery", "tender box"])
    has_document = bool(tender.get("document_url")) or ".pdf" in blob or "download" in blob

    allowed = bool(pattern_hits or has_closing or has_document or has_submission)

    if listing_hits and not (pattern_hits or has_closing or has_document):
        allowed = False

    return {
        "allowed": allowed,
        "reason": "real_rfq_evidence_found" if allowed else "real_rfq_evidence_missing",
        "pattern_hits": pattern_hits,
        "has_closing": has_closing,
        "has_submission": has_submission,
        "has_document": has_document,
        "listing_hits": listing_hits,
    }


'''


def main():
    if not TARGET.exists():
        raise FileNotFoundError(f"Missing {TARGET}")

    text = TARGET.read_text()
    backup = TARGET.with_suffix(TARGET.suffix + f".backup_before_real_rfq_filter_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    backup.write_text(text)
    print(f"Backup created: {backup}")

    if "def _has_real_rfq_evidence" not in text:
        marker = "def _is_strict_supply_candidate"
        idx = text.find(marker)
        if idx == -1:
            raise RuntimeError("Could not find strict supply filter marker.")
        text = text[:idx] + NEW_HELPER + "\n" + text[idx:]

    old = '''    if non_supply_hits:
        return {
            "allowed": False,
            "reason": "strict_supply_filter_non_supply",
            "supply_hits": supply_hits,
            "non_supply_hits": non_supply_hits,
        }

    if not supply_hits:
        return {
            "allowed": False,
            "reason": "strict_supply_filter_no_supply_keywords",
            "supply_hits": [],
            "non_supply_hits": [],
        }

    return {
        "allowed": True,
        "reason": "strict_supply_filter_allowed",
        "supply_hits": supply_hits,
        "non_supply_hits": [],
    }
'''

    new = '''    rfq_evidence = _has_real_rfq_evidence(tender)

    if non_supply_hits:
        return {
            "allowed": False,
            "reason": "strict_supply_filter_non_supply",
            "supply_hits": supply_hits,
            "non_supply_hits": non_supply_hits,
            "rfq_evidence": rfq_evidence,
        }

    if not supply_hits:
        return {
            "allowed": False,
            "reason": "strict_supply_filter_no_supply_keywords",
            "supply_hits": [],
            "non_supply_hits": [],
            "rfq_evidence": rfq_evidence,
        }

    if not rfq_evidence.get("allowed"):
        return {
            "allowed": False,
            "reason": "strict_supply_filter_no_real_rfq_evidence",
            "supply_hits": supply_hits,
            "non_supply_hits": [],
            "rfq_evidence": rfq_evidence,
        }

    return {
        "allowed": True,
        "reason": "strict_supply_filter_allowed_real_rfq",
        "supply_hits": supply_hits,
        "non_supply_hits": [],
        "rfq_evidence": rfq_evidence,
    }
'''

    if "strict_supply_filter_no_real_rfq_evidence" not in text:
        if old not in text:
            raise RuntimeError("Could not find strict supply return block to replace.")
        text = text.replace(old, new, 1)

    if "import re" not in text:
        lines = text.splitlines(keepends=True)
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                insert_at = i + 1
        lines.insert(insert_at, "import re\n")
        text = "".join(lines)

    TARGET.write_text(text)
    print("Real RFQ detection filter wired into safe scheduler.")


if __name__ == "__main__":
    main()
