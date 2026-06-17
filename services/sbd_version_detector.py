import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from pypdf import PdfReader


@dataclass
class SBDVersionDetectionResult:
    path: str
    filename: str
    form_code: Optional[str]
    detected_version: Optional[str]
    profile_key: Optional[str]
    profile_name: Optional[str]
    confidence: float
    matched_markers: List[str]
    extracted_text_preview: str
    status: str
    reason: str


class SBDVersionDetector:
    """
    Detect SBD form family and version from PDF content.

    Current support:
    - SBD4 new: "Bidder's Disclosure"
    - SBD4 old: "Declaration of Interest"
    """

    DEFAULT_PROFILE_ROUTER = {
        "sbd4_old": "sbd4_old_profile.json",
        "sbd4_new": "sbd4_new_profile.json",
        "sbd4": "example_sbd4_profile.json",
    }

    def __init__(self, profile_router: Optional[Dict[str, str]] = None) -> None:
        self.profile_router = profile_router or dict(self.DEFAULT_PROFILE_ROUTER)

    def detect_file(self, path: str) -> Dict[str, Any]:
        file_path = Path(path)

        if not file_path.exists():
            return asdict(
                SBDVersionDetectionResult(
                    path=path,
                    filename=file_path.name,
                    form_code=None,
                    detected_version=None,
                    profile_key=None,
                    profile_name=None,
                    confidence=0.0,
                    matched_markers=[],
                    extracted_text_preview="",
                    status="missing_file",
                    reason="File does not exist",
                )
            )

        if file_path.suffix.lower() != ".pdf":
            return asdict(
                SBDVersionDetectionResult(
                    path=path,
                    filename=file_path.name,
                    form_code=None,
                    detected_version=None,
                    profile_key=None,
                    profile_name=None,
                    confidence=0.0,
                    matched_markers=[],
                    extracted_text_preview="",
                    status="unsupported_file_type",
                    reason="Only PDF detection is currently supported",
                )
            )

        extracted_text = self.extract_text(path)
        normalized_text = self._normalize_text(extracted_text)
        filename_norm = self._normalize_text(file_path.name)

        form_code = self._detect_form_code(normalized_text, filename_norm)

        if form_code != "sbd4":
            return asdict(
                SBDVersionDetectionResult(
                    path=path,
                    filename=file_path.name,
                    form_code=form_code,
                    detected_version=None,
                    profile_key=None,
                    profile_name=None,
                    confidence=0.35 if form_code else 0.0,
                    matched_markers=[],
                    extracted_text_preview=extracted_text[:1000],
                    status="detected_form_but_no_version_logic" if form_code else "no_form_detected",
                    reason=(
                        f"Detected form '{form_code}', but no version classifier exists yet"
                        if form_code
                        else "Could not detect supported SBD form from file"
                    ),
                )
            )

        version_result = self._detect_sbd4_version(normalized_text)
        profile_key = f"sbd4_{version_result['version']}" if version_result["version"] else None
        profile_name = self.profile_router.get(profile_key) if profile_key else self.profile_router.get("sbd4")

        return asdict(
            SBDVersionDetectionResult(
                path=path,
                filename=file_path.name,
                form_code="sbd4",
                detected_version=version_result["version"],
                profile_key=profile_key,
                profile_name=profile_name,
                confidence=version_result["confidence"],
                matched_markers=version_result["markers"],
                extracted_text_preview=extracted_text[:1000],
                status="success" if version_result["version"] else "manual_review_required",
                reason=version_result["reason"],
            )
        )

    def detect_folder(self, root_path: str) -> Dict[str, Any]:
        root = Path(root_path)

        if not root.exists():
            return {
                "status": "missing_folder",
                "root_path": root_path,
                "results": [],
                "notes": ["Folder does not exist"],
            }

        results: List[Dict[str, Any]] = []
        for path in sorted(root.rglob("*.pdf")):
            results.append(self.detect_file(str(path)))

        return {
            "status": "success",
            "root_path": str(root),
            "results": results,
            "notes": [
                "SBD4 old/new detection uses document content first, not filename only.",
                "Current logic: 'Bidder’s Disclosure' => new format; 'Declaration of Interest' without bidder disclosure => old format.",
            ],
        }

    def extract_text(self, path: str) -> str:
        reader = PdfReader(path)
        chunks: List[str] = []

        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if text:
                chunks.append(text)

        return "\n".join(chunks)

    def _detect_form_code(self, normalized_text: str, filename_norm: str) -> Optional[str]:
        combined = f"{filename_norm} {normalized_text}"

        if self._contains_any(
            combined,
            [
                "standard bidding document sbd 4",
                "standard bidding document sbd4",
                "sbd 4",
                "sbd4",
                "declaration of interest",
                "bidder s disclosure",
                "bidders disclosure",
                "bidder disclosure",
            ],
        ):
            return "sbd4"

        if self._contains_any(
            combined,
            [
                "sbd 8",
                "sbd8",
                "past supply chain management practices",
            ],
        ):
            return "sbd8"

        if self._contains_any(
            combined,
            [
                "sbd 9",
                "sbd9",
                "certificate of independent bid determination",
            ],
        ):
            return "sbd9"

        if self._contains_any(
            combined,
            [
                "sbd 6.1",
                "sbd 6 1",
                "sbd6.1",
                "preference points claim form",
            ],
        ):
            return "sbd6_1"

        return None

    def _detect_sbd4_version(self, normalized_text: str) -> Dict[str, Any]:
        markers: List[str] = []

        new_markers = [
            "bidder s disclosure",
            "bidders disclosure",
            "bidder disclosure",
            "3 declaration",
            "i certify that the information furnished",
            "name of bidder",
            "signature",
            "position",
            "date",
        ]

        old_markers = [
            "declaration of interest",
            "sbd 4 declaration of interest",
        ]

        matched_new = [m for m in new_markers if m in normalized_text]
        matched_old = [m for m in old_markers if m in normalized_text]

        if matched_new:
            markers.extend(matched_new)
        if matched_old:
            markers.extend(matched_old)

        if len(matched_new) >= 2:
            return {
                "version": "new",
                "confidence": min(0.9 + (0.02 * len(matched_new)), 0.99),
                "markers": matched_new,
                "reason": "Detected SBD4 new format via bidder disclosure/declaration markers",
            }

        if len(matched_old) >= 1 and not matched_new:
            return {
                "version": "old",
                "confidence": 0.93,
                "markers": matched_old,
                "reason": "Detected SBD4 old format from declaration of interest wording",
            }

        if matched_old and matched_new:
            return {
                "version": "new",
                "confidence": 0.7,
                "markers": matched_new + matched_old,
                "reason": "Both old and new markers appeared; defaulted to new because bidder disclosure markers were present",
            }

        return {
            "version": None,
            "confidence": 0.0,
            "markers": markers,
            "reason": "Could not confidently determine whether SBD4 is old or new format",
        }

    def _normalize_text(self, text: str) -> str:
        text = (text or "").lower()
        text = text.replace("&", " and ")
        text = text.replace("’", "'")
        text = text.replace("‘", "'")
        text = re.sub(r"[\r\n\t]+", " ", text)
        text = re.sub(r"[^a-z0-9' ]+", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _contains_any(self, text: str, candidates: List[str]) -> bool:
        return any(self._normalize_text(c) in text for c in candidates)
