from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from pypdf import PdfReader


@dataclass
class DetectedForm:
    form_code: str
    confidence: float
    buyer_family: str
    stamp_allowed: bool
    witness_required: bool
    suggested_profile: Optional[str]
    matched_signals: List[str]
    page_index: Optional[int] = None


class SBDAutoDetectionEngine:
    """
    Detects common South African bid/tender form types from PDF text.

    Output is intended to drive:
    - profile selection
    - stamp application rules
    - witness-signature rules
    """

    FORM_RULES = [
        {
            "form_code": "mbd_1",
            "buyer_family": "municipal",
            "signals": [
                r"\bmbd\s*1\b",
                r"\binvitation to bid\b",
                r"\bmunicipal\b",
            ],
            "stamp_allowed": True,
            "witness_required": False,
            "suggested_profile": "municipal_mbd1_profile.json",
        },
        {
            "form_code": "mbd_4",
            "buyer_family": "municipal",
            "signals": [
                r"\bmbd\s*4\b",
                r"\bdeclaration of interest\b",
            ],
            "stamp_allowed": True,
            "witness_required": True,
            "suggested_profile": "municipal_mbd4_profile.json",
        },
        {
            "form_code": "mbd_6_1",
            "buyer_family": "municipal",
            "signals": [
                r"\bmbd\s*6(?:\.|_)?1\b",
                r"\bpreference points claim form\b",
                r"\bpreferential procurement\b",
            ],
            "stamp_allowed": True,
            "witness_required": False,
            "suggested_profile": "municipal_mbd6_1_profile.json",
        },
        {
            "form_code": "mbd_8",
            "buyer_family": "municipal",
            "signals": [
                r"\bmbd\s*8\b",
                r"\bdeclaration of bidder[‚Äô']?s past supply chain management practices\b",
            ],
            "stamp_allowed": True,
            "witness_required": True,
            "suggested_profile": "municipal_mbd8_profile.json",
        },
        {
            "form_code": "mbd_9",
            "buyer_family": "municipal",
            "signals": [
                r"\bmbd\s*9\b",
                r"\bcertificate of independent bid determination\b",
            ],
            "stamp_allowed": True,
            "witness_required": True,
            "suggested_profile": "municipal_mbd9_profile.json",
        },
        {
            "form_code": "sbd_1",
            "buyer_family": "national_or_provincial",
            "signals": [
                r"\bsbd\s*1\b",
                r"\binvitation to bid\b",
            ],
            "stamp_allowed": True,
            "witness_required": False,
            "suggested_profile": "sbd1_profile.json",
        },
        {
            "form_code": "sbd_4",
            "buyer_family": "national_or_provincial",
            "signals": [
                r"\bsbd\s*4\b",
                r"\bbidders disclosure\b",
                r"\bdeclaration of interest\b",
            ],
            "stamp_allowed": True,
            "witness_required": True,
            "suggested_profile": "sbd4_profile.json",
        },
        {
            "form_code": "sbd_6_1",
            "buyer_family": "national_or_provincial",
            "signals": [
                r"\bsbd\s*6(?:\.|_)?1\b",
                r"\bpreference points claim form\b",
            ],
            "stamp_allowed": True,
            "witness_required": False,
            "suggested_profile": "sbd6_1_profile.json",
        },
        {
            "form_code": "sbd_8",
            "buyer_family": "national_or_provincial",
            "signals": [
                r"\bsbd\s*8\b",
                r"\bdeclaration of bidder[‚Äô']?s past supply chain management practices\b",
            ],
            "stamp_allowed": True,
            "witness_required": True,
            "suggested_profile": "sbd8_profile.json",
        },
        {
            "form_code": "sbd_9",
            "buyer_family": "national_or_provincial",
            "signals": [
                r"\bsbd\s*9\b",
                r"\bcertificate of independent bid determination\b",
            ],
            "stamp_allowed": True,
            "witness_required": True,
            "suggested_profile": "sbd9_profile.json",
        },
        {
            "form_code": "authority_to_sign",
            "buyer_family": "generic",
            "signals": [
                r"\bauthority to sign\b",
                r"\bcertificate of authority\b",
                r"\bcapacity under which this bid is signed\b",
            ],
            "stamp_allowed": True,
            "witness_required": True,
            "suggested_profile": "authority_to_sign_profile.json",
        },
        {
            "form_code": "pricing_schedule",
            "buyer_family": "generic",
            "signals": [
                r"\bpricing schedule\b",
                r"\bfirm prices\b",
                r"\bprice schedule\b",
                r"\bbill of quantities\b",
            ],
            "stamp_allowed": True,
            "witness_required": False,
            "suggested_profile": "pricing_schedule_profile.json",
        },
        {
            "form_code": "eskom_itt",
            "buyer_family": "eskom",
            "signals": [
                r"\beskom holdings soc ltd\b",
                r"\binvitation to tender\b",
                r"\be-\s*tendering\b|\be\s*tendering\b",
            ],
            "stamp_allowed": False,
            "witness_required": False,
            "suggested_profile": None,
        },
    ]

    @classmethod
    def detect_pdf(cls, input_path: str, max_pages: int = 25) -> List[DetectedForm]:
        pdf_path = Path(input_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {input_path}")

        reader = PdfReader(str(pdf_path))
        results: List[DetectedForm] = []

        max_page_count = min(max_pages, len(reader.pages))
        for page_index in range(max_page_count):
            page = reader.pages[page_index]
            try:
                raw_text = page.extract_text() or ""
            except Exception:
                raw_text = ""

            page_text = cls._normalize_text(raw_text)
            if not page_text.strip():
                continue

            detected = cls._detect_from_text(page_text=page_text, page_index=page_index)
            if detected:
                results.extend(detected)

        return cls._dedupe_results(results)

    @classmethod
    def detect_text(cls, text: str) -> List[DetectedForm]:
        return cls._detect_from_text(cls._normalize_text(text), page_index=None)

    @classmethod
    def choose_best_profile(cls, detections: List[DetectedForm]) -> Optional[str]:
        if not detections:
            return None
        ranked = sorted(detections, key=lambda x: x.confidence, reverse=True)
        return ranked[0].suggested_profile

    @classmethod
    def _detect_from_text(cls, page_text: str, page_index: Optional[int]) -> List[DetectedForm]:
        found: List[DetectedForm] = []

        for rule in cls.FORM_RULES:
            matched_signals = []
            for pattern in rule["signals"]:
                if re.search(pattern, page_text, flags=re.IGNORECASE):
                    matched_signals.append(pattern)

            if not matched_signals:
                continue

            confidence = min(0.99, 0.35 + (0.2 * len(matched_signals)))
            found.append(
                DetectedForm(
                    form_code=rule["form_code"],
                    confidence=confidence,
                    buyer_family=rule["buyer_family"],
                    stamp_allowed=rule["stamp_allowed"],
                    witness_required=rule["witness_required"],
                    suggested_profile=rule["suggested_profile"],
                    matched_signals=matched_signals,
                    page_index=page_index,
                )
            )

        return found

    @classmethod
    def _dedupe_results(cls, results: List[DetectedForm]) -> List[DetectedForm]:
        best_by_code: Dict[str, DetectedForm] = {}
        for item in results:
            existing = best_by_code.get(item.form_code)
            if existing is None or item.confidence > existing.confidence:
                best_by_code[item.form_code] = item

        return sorted(
            best_by_code.values(),
            key=lambda x: (x.page_index if x.page_index is not None else 9999, -x.confidence),
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = (text or "").lower()
        text = text.replace("‚Äô", "'").replace("‚Äò", "'")
        text = re.sub(r"\s+", " ", text)
        return text.strip()


