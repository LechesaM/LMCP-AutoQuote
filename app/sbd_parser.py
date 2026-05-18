from __future__ import annotations

import re
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from app.sbd_models import TenderSBDRequirement
from app.sbd_registry import KEYWORD_MAP, SBD_REGISTRY


def normalize_text(text: str) -> str:
    return (text or "").lower().strip()


def detect_sbd_forms_from_text(text: str) -> List[Tuple[str, str]]:
    detected = []
    haystack = normalize_text(text)

    for form_code, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw in haystack:
                detected.append((form_code, kw))
                break

    return detected


def detect_preference_points(text: str) -> bool:
    haystack = normalize_text(text)
    patterns = [
        r"80/20",
        r"90/10",
        r"preference points",
        r"preferential procurement",
        r"b-bbee",
        r"bbbee",
    ]
    return any(re.search(p, haystack) for p in patterns)


def build_requirement_list_from_opportunity(opportunity) -> List[Dict]:
    title = getattr(opportunity, "title", "") or ""
    description = getattr(opportunity, "description", "") or ""
    text = f"{title}\n{description}"

    found = detect_sbd_forms_from_text(text)

    requirements = []
    already = set()

    for form_code, source in found:
        requirements.append(
            {
                "form_code": form_code,
                "required": True,
                "detected": True,
                "source_file": "opportunity_text",
                "version": SBD_REGISTRY[form_code]["version"],
                "notes": f"Detected by keyword: {source}",
            }
        )
        already.add(form_code)

    if detect_preference_points(text) and "SBD6.1" not in already:
        requirements.append(
            {
                "form_code": "SBD6.1",
                "required": True,
                "detected": True,
                "source_file": "opportunity_text",
                "version": SBD_REGISTRY["SBD6.1"]["version"],
                "notes": "Detected from preference points / B-BBEE language.",
            }
        )
        already.add("SBD6.1")

    default_core = ["SBD1", "SBD4", "SBD8", "SBD9"]
    for form_code in default_core:
        if form_code not in already:
            requirements.append(
                {
                    "form_code": form_code,
                    "required": False,
                    "detected": False,
                    "source_file": "system_default",
                    "version": SBD_REGISTRY[form_code]["version"],
                    "notes": "Added as standard default pending manual confirmation.",
                }
            )

    return requirements


def upsert_sbd_requirements(db: Session, opportunity_id: int, requirements: List[Dict]) -> List[TenderSBDRequirement]:
    rows: List[TenderSBDRequirement] = []

    for item in requirements:
        row = (
            db.query(TenderSBDRequirement)
            .filter(
                TenderSBDRequirement.opportunity_id == opportunity_id,
                TenderSBDRequirement.form_code == item["form_code"],
            )
            .first()
        )

        if row is None:
            row = TenderSBDRequirement(
                opportunity_id=opportunity_id,
                form_code=item["form_code"],
            )
            db.add(row)

        row.required = item.get("required", True)
        row.detected = item.get("detected", False)
        row.source_file = item.get("source_file")
        row.version = item.get("version")
        row.notes = item.get("notes")
        row.status = "pending"

        rows.append(row)

    db.commit()

    for row in rows:
        db.refresh(row)

    return rows
