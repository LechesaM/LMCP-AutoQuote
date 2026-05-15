from pathlib import Path
from datetime import datetime

TARGET = Path("app/services/safe_autonomous_scheduler_service.py")

HELPER = '''
SUPPLY_HARVEST_KEYWORDS = [
    "supply and delivery",
    "supply",
    "delivery",
    "procurement",
    "provide and deliver",
    "appointment of service provider for supply",
    "purchase",
    "quotation for supply",
    "rfq supply",
]

NON_SUPPLY_HARVEST_KEYWORDS = [
    "repair",
    "installation",
    "maintenance",
    "consultation",
    "consulting",
    "meeting invitation",
    "request for information",
    "rfi",
    "archive",
    "tenders archive",
    "tender portal",
    "rfq/tenders",
    "database",
    "panel of service providers",
    "expression of interest",
    "training",
    "workshop",
]


def _is_strict_supply_candidate(tender: Dict[str, Any]) -> Dict[str, Any]:
    blob = " ".join(
        str(tender.get(k) or "")
        for k in [
            "buyer_rfq_number",
            "rfq_number",
            "reference_number",
            "title",
            "description",
            "raw_text",
            "category",
            "tender_category",
            "portal_name",
            "source_name",
        ]
    ).lower()

    non_supply_hits = [kw for kw in NON_SUPPLY_HARVEST_KEYWORDS if kw in blob]
    supply_hits = [kw for kw in SUPPLY_HARVEST_KEYWORDS if kw in blob]

    if non_supply_hits:
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


def _apply_strict_supply_filter(tenders: List[Dict[str, Any]]) -> Dict[str, Any]:
    allowed: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    for tender in tenders:
        decision = _is_strict_supply_candidate(tender)
        if decision.get("allowed"):
            tender = dict(tender)
            tender["strict_supply_filter"] = decision
            allowed.append(tender)
        else:
            rejected.append({
                "buyer_rfq_number": tender.get("buyer_rfq_number") or tender.get("rfq_number") or tender.get("reference_number") or tender.get("title"),
                "title": tender.get("title"),
                "decision": decision,
            })

    return {
        "allowed": allowed,
        "rejected": rejected,
        "allowed_count": len(allowed),
        "rejected_count": len(rejected),
    }


'''


def main():
    if not TARGET.exists():
        raise FileNotFoundError(f"Missing {TARGET}")

    text = TARGET.read_text()

    backup = TARGET.with_suffix(TARGET.suffix + f".backup_before_strict_supply_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    backup.write_text(text)
    print(f"Backup created: {backup}")

    if "def _is_strict_supply_candidate" not in text:
        marker = "async def _safe_harvest"
        idx = text.find(marker)
        if idx == -1:
            raise RuntimeError("Could not find async def _safe_harvest marker.")
        text = text[:idx] + HELPER + "\n" + text[idx:]

    old = '''            tenders = harvest.get("tenders", [])
            run["summary"]["harvested"] = len(tenders)
            submissions_used = 0
'''

    new = '''            tenders = harvest.get("tenders", [])
            run["summary"]["harvested"] = len(tenders)

            strict_supply = _apply_strict_supply_filter(tenders)
            tenders = strict_supply.get("allowed", [])
            run["strict_supply_filter"] = {
                "allowed_count": strict_supply.get("allowed_count", 0),
                "rejected_count": strict_supply.get("rejected_count", 0),
                "rejected": strict_supply.get("rejected", [])[:25],
            }
            run["summary"]["supply_candidates"] = len(tenders)
            run["summary"]["non_supply_rejected"] = strict_supply.get("rejected_count", 0)

            submissions_used = 0
'''

    if 'run["strict_supply_filter"]' not in text:
        if old not in text:
            raise RuntimeError("Could not find tender assignment block to patch.")
        text = text.replace(old, new, 1)

    TARGET.write_text(text)
    print("Strict supply harvesting filter wired into safe scheduler.")


if __name__ == "__main__":
    main()
