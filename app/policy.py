import re
from dataclasses import dataclass

# Conservative allow/deny patterns.
# We only allow email submission if the RFQ explicitly says to submit/return/email responses to an address.
ALLOW_PATTERNS = [
    r"submit\s+(your\s+)?(quotation|quote|proposal|bid|response)\s+by\s+email",
    r"email\s+(your\s+)?(quotation|quote|proposal|bid|response)\s+to",
    r"send\s+(your\s+)?(quotation|quote|proposal|bid|response)\s+to\s+.*@",
    r"(responses?|submissions?)\s+must\s+be\s+emailed\s+to",
    r"e-?mail\s+address\s*:\s*\S+@\S+",
]

DENY_PATTERNS = [
    r"do\s+not\s+email",
    r"no\s+email\s+submissions?",
    r"submissions?\s+via\s+email\s+will\s+not\s+be\s+accepted",
    r"only\s+via\s+(the\s+)?portal",
    r"submit\s+only\s+on\s+(the\s+)?e-?tender",
    r"hand\s+deliver",
]

@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str

def email_submission_allowed(text: str) -> PolicyDecision:
    t = (text or "").lower()

    for pat in DENY_PATTERNS:
        if re.search(pat, t, flags=re.IGNORECASE):
            return PolicyDecision(False, f"Denied by pattern: {pat}")

    for pat in ALLOW_PATTERNS:
        if re.search(pat, t, flags=re.IGNORECASE):
            return PolicyDecision(True, f"Allowed by pattern: {pat}")

    return PolicyDecision(False, "Not explicitly allowed (conservative default)")
