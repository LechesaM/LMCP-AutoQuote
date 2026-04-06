import re
from app.config import settings

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)

def is_soe(buyer_name: str) -> bool:
    b = (buyer_name or "").lower()
    return any(x.lower() in b for x in settings.soe_allowlist)

def is_supply_delivery(title: str, description: str) -> bool:
    text = f"{title or ''} {description or ''}".lower()
    return any(k.lower() in text for k in settings.delivery_keywords)

def extract_emails(*texts: str) -> list[str]:
    found = []
    for t in texts:
        if not t:
            continue
        found.extend(EMAIL_RE.findall(t))
    # dedupe while preserving order
    seen=set()
    out=[]
    for e in found:
        e=e.strip()
        if e.lower() not in seen:
            seen.add(e.lower())
            out.append(e)
    return out

if rfq.get("briefing_required") is True:
    return False

if estimated_profit < 30000:
    return False
