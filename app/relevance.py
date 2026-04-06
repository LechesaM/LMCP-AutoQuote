from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from app.submission_detection import detect_email_submission


LMCP_POSITIVE_KEYWORDS: List[Tuple[str, int]] = [
    ("supply", 18),
    ("delivery", 18),
    ("supply and delivery", 28),
    ("supply & delivery", 28),
    ("supply, delivery", 24),
    ("deliver", 10),
    ("procurement", 8),
    ("goods", 10),
    ("purchase", 8),
    ("supply of", 16),
    ("delivery of", 16),
    ("appointment of service provider for supply", 12),
    ("request for quotation", 8),
    ("rfq", 8),
    ("quotation", 6),
    ("bid", 4),
    ("tender", 4),
    ("materials", 10),
    ("equipment", 10),
    ("tools", 8),
    ("consumables", 10),
    ("stationery", 8),
    ("furniture", 8),
    ("ict equipment", 10),
    ("laptops", 10),
    ("printers", 10),
    ("network equipment", 10),
    ("ppe", 12),
    ("protective clothing", 12),
    ("uniform", 10),
    ("electrical material", 12),
    ("plumbing material", 12),
    ("building material", 12),
    ("water treatment chemicals", 12),
    ("chemicals", 8),
    ("pipes", 10),
    ("valves", 10),
    ("generators", 10),
    ("inverters", 10),
    ("solar", 8),
    ("office equipment", 10),
    ("medical supplies", 10),
    ("cleaning materials", 10),
    ("road signs", 10),
    ("permanent road signs", 14),
    ("traffic accommodation items", 12),
]

LMCP_NEGATIVE_KEYWORDS: List[Tuple[str, int]] = [
    ("consulting", -18),
    ("consultancy", -18),
    ("professional services", -15),
    ("training", -18),
    ("facilitation", -15),
    ("workshop", -12),
    ("legal services", -22),
    ("audit services", -18),
    ("accounting services", -18),
    ("insurance services", -18),
    ("banking services", -18),
    ("security services", -18),
    ("cleaning services", -14),
    ("travel management", -16),
    ("catering services", -12),
    ("advertising", -14),
    ("media buying", -14),
    ("recruitment", -16),
    ("hr services", -16),
    ("software development", -12),
    ("maintenance only", -16),
    ("repair only", -16),
    ("construction", -14),
    ("civil works", -18),
    ("building works", -18),
    ("refurbishment", -16),
    ("renovation", -16),
    ("as and when required services", -12),
    ("panel of service providers", -12),
]

PREFERRED_BUYERS: List[str] = [
    "department",
    "municipality",
    "local municipality",
    "district municipality",
    "metropolitan municipality",
    "state owned",
    "state-owned",
    "soc",
    "soe",
    "government",
    "public works",
    "human settlements",
    "water",
    "sanitation",
    "roads",
    "health",
    "education",
    "saps",
    "transnet",
    "eskom",
    "sanral",
    "prasa",
    "csir",
    "necsa",
    "national museum",
]

SUPPLY_CATEGORIES: List[str] = [
    "supplies",
    "goods",
    "procurement",
    "material",
    "equipment",
    "consumables",
    "inventory",
    "asset",
]


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def build_opportunity_text(opportunity: Any) -> str:
    parts = [
        getattr(opportunity, "title", ""),
        getattr(opportunity, "description", ""),
        getattr(opportunity, "buyer_name", ""),
        getattr(opportunity, "category", ""),
        getattr(opportunity, "source", ""),
        getattr(opportunity, "source_url", ""),
        getattr(opportunity, "reference_no", ""),
    ]
    return normalize_text(" | ".join([p for p in parts if p]))


def keyword_score(text: str, keywords: List[Tuple[str, int]]) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []

    for phrase, weight in keywords:
        if phrase in text:
            score += weight
            reasons.append(f"{phrase} ({weight:+d})")

    return score, reasons


def buyer_score(text: str) -> Tuple[int, List[str]]:
    reasons: List[str] = []
    score = 0

    for buyer_hint in PREFERRED_BUYERS:
        if buyer_hint in text:
            score += 4
            reasons.append(f"preferred buyer signal: {buyer_hint} (+4)")

    return min(score, 16), reasons


def category_score(text: str) -> Tuple[int, List[str]]:
    reasons: List[str] = []
    score = 0

    for hint in SUPPLY_CATEGORIES:
        if hint in text:
            score += 4
            reasons.append(f"supply category signal: {hint} (+4)")

    return min(score, 12), reasons


def title_bonus(title: str) -> Tuple[int, List[str]]:
    reasons: List[str] = []
    score = 0
    t = normalize_text(title)

    strong_patterns = [
        "supply and delivery",
        "supply & delivery",
        "appointment for supply and delivery",
        "appointment of a service provider for the supply",
        "request for quotation for supply",
        "appointment of supplier",
    ]

    for pattern in strong_patterns:
        if pattern in t:
            score += 12
            reasons.append(f"title strong match: {pattern} (+12)")

    return min(score, 24), reasons


def deadline_bonus(opportunity: Any) -> Tuple[int, List[str]]:
    if getattr(opportunity, "closing_date", None):
        return 4, ["has closing date (+4)"]
    return 0, []


def reference_bonus(opportunity: Any) -> Tuple[int, List[str]]:
    ref = normalize_text(getattr(opportunity, "reference_no", ""))
    if ref:
        return 3, ["has reference number (+3)"]
    return 0, []


def source_bonus(opportunity: Any) -> Tuple[int, List[str]]:
    src = normalize_text(getattr(opportunity, "source", ""))
    if not src:
        return 0, []
    return 3, [f"known source: {src} (+3)"]


def classify_score(score: int) -> str:
    if score >= 75:
        return "HIGH"
    if score >= 50:
        return "MEDIUM"
    return "LOW"


def clamp_score(score: int) -> int:
    return max(0, min(100, score))


def compute_relevance(opportunity: Any) -> Dict[str, Any]:
    title = getattr(opportunity, "title", "")
    text = build_opportunity_text(opportunity)

    total = 0
    reasons: List[str] = []

    pos_score, pos_reasons = keyword_score(text, LMCP_POSITIVE_KEYWORDS)
    neg_score, neg_reasons = keyword_score(text, LMCP_NEGATIVE_KEYWORDS)
    b_score, b_reasons = buyer_score(text)
    c_score, c_reasons = category_score(text)
    t_score, t_reasons = title_bonus(title)
    d_score, d_reasons = deadline_bonus(opportunity)
    r_score, r_reasons = reference_bonus(opportunity)
    s_score, s_reasons = source_bonus(opportunity)

    total += pos_score
    total += neg_score
    total += b_score
    total += c_score
    total += t_score
    total += d_score
    total += r_score
    total += s_score

    reasons.extend(pos_reasons)
    reasons.extend(neg_reasons)
    reasons.extend(b_reasons)
    reasons.extend(c_reasons)
    reasons.extend(t_reasons)
    reasons.extend(d_reasons)
    reasons.extend(r_reasons)
    reasons.extend(s_reasons)

    if "supply and delivery" in text or "supply & delivery" in text:
        total += 10
        reasons.append("direct LMCP fit: supply and delivery (+10)")

    has_supply_signal = any(
        phrase in text
        for phrase, _ in LMCP_POSITIVE_KEYWORDS
        if "supply" in phrase or "delivery" in phrase or "goods" in phrase
    )
    has_service_signal = any(
        phrase in text
        for phrase in [
            "services",
            "consulting",
            "consultancy",
            "training",
            "maintenance",
            "support services",
            "professional services",
        ]
    )

    if has_service_signal and not has_supply_signal:
        total -= 20
        reasons.append("service-heavy tender without clear goods supply (-20)")

    # Email submission boost
    email_meta = detect_email_submission(opportunity)
    if email_meta["allows_email_submission"]:
        total += 18
        reasons.append("email submission allowed (+18)")
    elif email_meta["submission_emails"]:
        total += 5
        reasons.append("submission/contact email found (+5)")
    else:
        total -= 8
        reasons.append("no email submission signal (-8)")

    score = clamp_score(total)
    label = classify_score(score)

    return {
        "score": score,
        "label": label,
        "reasons": reasons[:25],
    }
