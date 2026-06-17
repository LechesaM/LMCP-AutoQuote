import json
import os
import re
import shutil
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

DEFAULT_FORMS_CATALOG = {
    "sbd1": {
        "aliases": [
            "sbd 1",
            "sbd1",
            "invitation to bid",
            "invitation for bid",
            "part a invitation to bid",
            "request for bid invitation"
        ],
        "standalone_templates": [
            "sbd1.pdf",
            "sbd1.docx"
        ],
    },
    "sbd4": {
        "aliases": [
            "sbd 4",
            "sbd4",
            "declaration of interest",
            "bidder's disclosure",
            "bidders disclosure"
        ],
        "standalone_templates": [
            "sbd4.pdf",
            "sbd4.docx"
        ],
    },
    "sbd6_1": {
        "aliases": [
            "sbd 6.1",
            "sbd6.1",
            "sbd6_1",
            "preference points claim form",
            "preference points",
            "b-bbee",
            "b-bbee status level"
        ],
        "standalone_templates": [
            "sbd6_1.pdf",
            "sbd6_1.docx"
        ],
    },
    "sbd6_2": {
        "aliases": [
            "sbd 6.2",
            "sbd6.2",
            "sbd6_2",
            "local production and content",
            "declaration certificate for local production"
        ],
        "standalone_templates": [
            "sbd6_2.pdf",
            "sbd6_2.docx"
        ],
    },
    "sbd8": {
        "aliases": [
            "sbd 8",
            "sbd8",
            "declaration of bidder's past supply chain management practices",
            "past supply chain management practices"
        ],
        "standalone_templates": [
            "sbd8.pdf",
            "sbd8.docx"
        ],
    },
    "sbd9": {
        "aliases": [
            "sbd 9",
            "sbd9",
            "certificate of independent bid determination",
            "independent bid determination"
        ],
        "standalone_templates": [
            "sbd9.pdf",
            "sbd9.docx"
        ],
    },
    "pricing_schedule": {
        "aliases": [
            "pricing schedule",
            "price schedule",
            "bill of quantities",
            "boq",
            "pricing document",
            "schedule of quantities"
        ],
        "standalone_templates": [
            "pricing_schedule.xlsx",
            "pricing_schedule.docx",
            "pricing_schedule.pdf"
        ],
    },
    "returnable_schedule": {
        "aliases": [
            "returnable schedule",
            "returnables",
            "returnable documents",
            "mandatory returnable documents"
        ],
        "standalone_templates": [],
    },
}


# -----------------------------------------------------------------------------
# Data Models
# -----------------------------------------------------------------------------

@dataclass
class TenderDocument:
    path: str
    filename: str
    ext: str
    size_bytes: int
    source: str = "tender_pack"
    extracted_from_archive: bool = False


@dataclass
class DetectedForm:
    form_code: str
    matched_alias: str
    path: str
    filename: str
    source: str
    confidence: float = 1.0


@dataclass
class RequiredForm:
    form_code: str
    reason: str
    required: bool = True


@dataclass
class MissingForm:
    form_code: str
    reason: str
    fallback_template_path: Optional[str] = None


@dataclass
class SubmissionDocument:
    path: str
    filename: str
    form_code: Optional[str]
    source: str
    priority: int
    selected: bool = True
    reason: str = ""


@dataclass
class TenderFormPriorityResult:
    tender_id: Optional[str]
    root_path: str
    documents_found: List[Dict[str, Any]] = field(default_factory=list)
    detected_forms: List[Dict[str, Any]] = field(default_factory=list)
    required_forms: List[Dict[str, Any]] = field(default_factory=list)
    missing_forms: List[Dict[str, Any]] = field(default_factory=list)
    selected_submission_documents: List[Dict[str, Any]] = field(default_factory=list)
    skipped_duplicates: List[Dict[str, Any]] = field(default_factory=list)
    generated_fallback_requests: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


# -----------------------------------------------------------------------------
# Engine
# -----------------------------------------------------------------------------

class TenderFormPriorityEngine:
    """
    Priority rules:
    1. Inspect the RFQ/tender pack first
    2. Detect forms already present in the pack
    3. Infer required forms from instructions/text + known mandatory forms
    4. Complete existing tender-pack forms first
    5. Generate standalone fallback forms only if required forms are missing
    6. Deduplicate the final submission pack
    """

    def __init__(
        self,
        forms_catalog: Optional[Dict[str, Dict[str, Any]]] = None,
        master_template_dir: str = "app/data/master_forms",
        extracted_dir_name: str = "_extracted_archives",
    ) -> None:
        self.forms_catalog = forms_catalog or DEFAULT_FORMS_CATALOG
        self.master_template_dir = Path(master_template_dir)
        self.extracted_dir_name = extracted_dir_name

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def build_submission_plan(
        self,
        tender_root: str,
        tender_id: Optional[str] = None,
        instructions_text: Optional[str] = None,
        mandatory_form_codes: Optional[List[str]] = None,
        enable_archive_extract: bool = True,
    ) -> Dict[str, Any]:
        root = Path(tender_root)
        if not root.exists():
            raise FileNotFoundError(f"Tender root not found: {tender_root}")

        docs = self.discover_documents(root, enable_archive_extract=enable_archive_extract)
        detected_forms = self.detect_embedded_forms(docs, instructions_text=instructions_text)
        required_forms = self.detect_required_forms_from_instructions(
            instructions_text=instructions_text,
            mandatory_form_codes=mandatory_form_codes or [],
        )

        selected_submission_documents, skipped_duplicates = self.select_priority_documents(
            docs=docs,
            detected_forms=detected_forms,
        )

        missing_forms = self.generate_only_missing_forms(
            required_forms=required_forms,
            selected_submission_documents=selected_submission_documents,
        )

        generated_fallback_requests = self.build_fallback_generation_requests(missing_forms)
        selected_submission_documents, skipped_more = self.deduplicate_submission_pack(
            selected_submission_documents=selected_submission_documents,
            generated_fallback_requests=generated_fallback_requests,
        )
        skipped_duplicates.extend(skipped_more)

        result = TenderFormPriorityResult(
            tender_id=tender_id,
            root_path=str(root),
            documents_found=[asdict(d) for d in docs],
            detected_forms=[asdict(f) for f in detected_forms],
            required_forms=[asdict(r) for r in required_forms],
            missing_forms=[asdict(m) for m in missing_forms],
            selected_submission_documents=[asdict(s) for s in selected_submission_documents],
            skipped_duplicates=skipped_duplicates,
            generated_fallback_requests=generated_fallback_requests,
            notes=self._build_notes(
                docs=docs,
                detected_forms=detected_forms,
                required_forms=required_forms,
                missing_forms=missing_forms,
            ),
        )
        return asdict(result)

    def discover_documents(
        self,
        tender_root: Path,
        enable_archive_extract: bool = True,
    ) -> List[TenderDocument]:
        discovered: List[TenderDocument] = []

        if enable_archive_extract:
            self._extract_archives_in_place(tender_root)

        for path in tender_root.rglob("*"):
            if not path.is_file():
                continue
            if self.extracted_dir_name in path.parts:
                source = "archive_extracted"
                extracted = True
            else:
                source = "tender_pack"
                extracted = False

            ext = path.suffix.lower()
            if ext not in {".pdf", ".docx", ".xlsx", ".xls", ".zip", ".doc", ".xlsm", ".txt", ".csv"}:
                continue

            try:
                size = path.stat().st_size
            except OSError:
                size = 0

            discovered.append(
                TenderDocument(
                    path=str(path),
                    filename=path.name,
                    ext=ext,
                    size_bytes=size,
                    source=source,
                    extracted_from_archive=extracted,
                )
            )

        discovered.sort(key=lambda d: (d.source != "tender_pack", d.filename.lower()))
        return discovered

    def detect_embedded_forms(
        self,
        docs: List[TenderDocument],
        instructions_text: Optional[str] = None,
    ) -> List[DetectedForm]:
        results: List[DetectedForm] = []
        seen: Set[Tuple[str, str]] = set()

        for doc in docs:
            searchable = self._normalize_text(f"{doc.filename} {self._safe_read_textish(doc.path)}")
            matched = self._detect_form_codes_in_text(searchable)

            for form_code, alias in matched:
                key = (form_code, doc.path)
                if key in seen:
                    continue
                seen.add(key)
                confidence = self._score_detected_form(doc.filename, searchable, alias)
                results.append(
                    DetectedForm(
                        form_code=form_code,
                        matched_alias=alias,
                        path=doc.path,
                        filename=doc.filename,
                        source=doc.source,
                        confidence=confidence,
                    )
                )

        if instructions_text:
            normalized_instructions = self._normalize_text(instructions_text)
            for form_code, alias in self._detect_form_codes_in_text(normalized_instructions):
                if not any(r.form_code == form_code for r in results):
                    continue

        results.sort(key=lambda r: (r.form_code, -r.confidence, r.filename.lower()))
        return results

    def detect_required_forms_from_instructions(
        self,
        instructions_text: Optional[str],
        mandatory_form_codes: List[str],
    ) -> List[RequiredForm]:
        required: Dict[str, RequiredForm] = {}

        for code in mandatory_form_codes:
            code_norm = self._normalize_form_code(code)
            if code_norm:
                required[code_norm] = RequiredForm(
                    form_code=code_norm,
                    reason="Specified as mandatory by system input",
                    required=True,
                )

        if instructions_text:
            norm_text = self._normalize_text(instructions_text)

            for form_code, alias in self._detect_form_codes_in_text(norm_text):
                if self._text_says_required(norm_text, alias):
                    required[form_code] = RequiredForm(
                        form_code=form_code,
                        reason=f"Detected as required in instructions via '{alias}'",
                        required=True,
                    )

            if self._contains_any(
                norm_text,
                [
                    "submit all sbd forms",
                    "all standard bidding documents",
                    "complete all sbd forms",
                ],
            ):
                for code in ["sbd1", "sbd4", "sbd8", "sbd9"]:
                    required.setdefault(
                        code,
                        RequiredForm(
                            form_code=code,
                            reason="Instructions imply all standard bidding documents are required",
                            required=True,
                        ),
                    )

            if self._contains_any(
                norm_text,
                ["pricing schedule", "bill of quantities", "boq", "price schedule"]
            ):
                required.setdefault(
                    "pricing_schedule",
                    RequiredForm(
                        form_code="pricing_schedule",
                        reason="Pricing schedule/BOQ referenced in instructions",
                        required=True,
                    ),
                )

        ordered = list(required.values())
        ordered.sort(key=lambda r: r.form_code)
        return ordered

    def select_priority_documents(
        self,
        docs: List[TenderDocument],
        detected_forms: List[DetectedForm],
    ) -> Tuple[List[SubmissionDocument], List[Dict[str, Any]]]:
        selected: List[SubmissionDocument] = []
        skipped: List[Dict[str, Any]] = []

        form_to_best_doc: Dict[str, DetectedForm] = {}
        for form in detected_forms:
            existing = form_to_best_doc.get(form.form_code)
            if not existing:
                form_to_best_doc[form.form_code] = form
                continue

            if self._prefer_form_candidate(form, existing):
                form_to_best_doc[form.form_code] = form

        selected_paths: Set[str] = set()
        for form_code, form in form_to_best_doc.items():
            priority = self._priority_for_form(form_code=form_code, source=form.source)
            selected.append(
                SubmissionDocument(
                    path=form.path,
                    filename=form.filename,
                    form_code=form_code,
                    source=form.source,
                    priority=priority,
                    selected=True,
                    reason="Prioritised existing form found in RFQ/tender pack",
                )
            )
            selected_paths.add(form.path)

        for doc in docs:
            if doc.path in selected_paths:
                continue

            doc_form_code = self._detect_form_code_from_filename(doc.filename)
            if doc_form_code and doc_form_code in form_to_best_doc:
                skipped.append(
                    {
                        "path": doc.path,
                        "filename": doc.filename,
                        "form_code": doc_form_code,
                        "reason": "Duplicate form found; existing tender-pack form already prioritised",
                    }
                )
                continue

            if self._looks_like_supporting_document(doc.filename):
                selected.append(
                    SubmissionDocument(
                        path=doc.path,
                        filename=doc.filename,
                        form_code=None,
                        source=doc.source,
                        priority=90,
                        selected=True,
                        reason="Supporting document retained in submission set",
                    )
                )

        selected.sort(key=lambda s: (s.priority, s.filename.lower()))
        return selected, skipped

    def generate_only_missing_forms(
        self,
        required_forms: List[RequiredForm],
        selected_submission_documents: List[SubmissionDocument],
    ) -> List[MissingForm]:
        present_form_codes = {
            s.form_code for s in selected_submission_documents if s.form_code
        }

        missing: List[MissingForm] = []
        for req in required_forms:
            if req.form_code in present_form_codes:
                continue

            fallback_template_path = self._find_master_template_for_form(req.form_code)
            missing.append(
                MissingForm(
                    form_code=req.form_code,
                    reason=f"Required form missing from tender pack. {req.reason}",
                    fallback_template_path=fallback_template_path,
                )
            )

        missing.sort(key=lambda m: m.form_code)
        return missing

    def build_fallback_generation_requests(
        self,
        missing_forms: List[MissingForm],
    ) -> List[Dict[str, Any]]:
        requests: List[Dict[str, Any]] = []
        for m in missing_forms:
            requests.append(
                {
                    "form_code": m.form_code,
                    "template_path": m.fallback_template_path,
                    "action": "generate_fallback_form" if m.fallback_template_path else "manual_review_required",
                    "reason": m.reason,
                }
            )
        return requests

    def deduplicate_submission_pack(
        self,
        selected_submission_documents: List[SubmissionDocument],
        generated_fallback_requests: List[Dict[str, Any]],
    ) -> Tuple[List[SubmissionDocument], List[Dict[str, Any]]]:
        final_selected = list(selected_submission_documents)
        skipped: List[Dict[str, Any]] = []
        existing_form_codes = {
            s.form_code for s in final_selected if s.form_code
        }

        for req in generated_fallback_requests:
            form_code = req["form_code"]
            if form_code in existing_form_codes:
                skipped.append(
                    {
                        "form_code": form_code,
                        "reason": "Fallback generation skipped because form already exists in selected submission set",
                    }
                )

        return final_selected, skipped

    # -------------------------------------------------------------------------
    # Helper: Policy
    # -------------------------------------------------------------------------

    def system_policy(self) -> str:
        return (
            "Always prioritise completing and submitting the forms contained in the RFQ or "
            "tender document pack. Do not generate or attach duplicate standalone SBD forms "
            "if the same required forms already exist in the tender pack. Only generate "
            "fallback forms when a required form is missing, unreadable, or explicitly "
            "requested separately."
        )

    # -------------------------------------------------------------------------
    # Helper: Archive Extraction
    # -------------------------------------------------------------------------

    def _extract_archives_in_place(self, tender_root: Path) -> None:
        for zip_path in tender_root.rglob("*.zip"):
            try:
                extract_base = zip_path.parent / self.extracted_dir_name / zip_path.stem
                extract_base.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(extract_base)
            except Exception:
                continue

    # -------------------------------------------------------------------------
    # Helper: Detection
    # -------------------------------------------------------------------------

    def _detect_form_codes_in_text(self, text: str) -> List[Tuple[str, str]]:
        matches: List[Tuple[str, str]] = []
        for form_code, cfg in self.forms_catalog.items():
            for alias in cfg.get("aliases", []):
                alias_norm = self._normalize_text(alias)
                if alias_norm and alias_norm in text:
                    matches.append((form_code, alias))
                    break
        return matches

    def _detect_form_code_from_filename(self, filename: str) -> Optional[str]:
        norm = self._normalize_text(filename)
        detected = self._detect_form_codes_in_text(norm)
        return detected[0][0] if detected else None

    def _score_detected_form(self, filename: str, searchable: str, alias: str) -> float:
        score = 0.5
        filename_norm = self._normalize_text(filename)
        alias_norm = self._normalize_text(alias)

        if alias_norm in filename_norm:
            score += 0.4
        if "sbd" in filename_norm:
            score += 0.1
        if "declaration" in searchable or "pricing" in searchable:
            score += 0.05
        return min(score, 1.0)

    def _prefer_form_candidate(self, candidate: DetectedForm, existing: DetectedForm) -> bool:
        if candidate.source == "tender_pack" and existing.source != "tender_pack":
            return True
        if candidate.confidence > existing.confidence:
            return True
        if candidate.confidence == existing.confidence and len(candidate.filename) < len(existing.filename):
            return True
        return False

    def _priority_for_form(self, form_code: str, source: str) -> int:
        if source == "tender_pack":
            return 10
        if source == "archive_extracted":
            return 20
        return 50

    def _find_master_template_for_form(self, form_code: str) -> Optional[str]:
        cfg = self.forms_catalog.get(form_code, {})
        candidates = cfg.get("standalone_templates", [])
        for candidate in candidates:
            path = self.master_template_dir / candidate
            if path.exists():
                return str(path)
        return None

    def _looks_like_supporting_document(self, filename: str) -> bool:
        norm = self._normalize_text(filename)
        keywords = [
            "tax",
            "csd",
            "cidb",
            "company profile",
            "profile",
            "reference",
            "ref letter",
            "supporting doc",
            "supporting document",
            "certificate",
            "registration",
            "letter of good standing",
            "bank rating",
            "financial statement",
            "broschure",
            "brochure",
        ]
        return any(self._normalize_text(k) in norm for k in keywords)

    def _text_says_required(self, normalized_text: str, alias: str) -> bool:
        alias_norm = self._normalize_text(alias)
        patterns = [
            f"must submit {alias_norm}",
            f"submit {alias_norm}",
            f"complete {alias_norm}",
            f"{alias_norm} must be completed",
            f"{alias_norm} is required",
            f"attach {alias_norm}",
            f"return {alias_norm}",
        ]
        return any(p in normalized_text for p in patterns)

    def _contains_any(self, text: str, candidates: List[str]) -> bool:
        norm_text = self._normalize_text(text)
        return any(self._normalize_text(c) in norm_text for c in candidates)

    def _normalize_form_code(self, value: str) -> str:
        value = value.strip().lower()
        value = value.replace("-", "_").replace(".", "_").replace(" ", "_")
        value = re.sub(r"[^a-z0-9_]", "", value)
        value = re.sub(r"_+", "_", value).strip("_")
        return value

    def _normalize_text(self, text: str) -> str:
        text = (text or "").lower()
        text = text.replace("&", " and ")
        text = re.sub(r"[\r\n\t]+", " ", text)
        text = re.sub(r"[^a-z0-9\. ]+", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _safe_read_textish(self, path: str) -> str:
        ext = Path(path).suffix.lower()
        try:
            if ext in {".txt", ".md", ".csv"}:
                return Path(path).read_text(encoding="utf-8", errors="ignore")[:25000]
            return Path(path).name
        except Exception:
            return Path(path).name

    def _build_notes(
        self,
        docs: List[TenderDocument],
        detected_forms: List[DetectedForm],
        required_forms: List[RequiredForm],
        missing_forms: List[MissingForm],
    ) -> List[str]:
        notes: List[str] = []
        notes.append(self.system_policy())
        notes.append(f"Documents discovered: {len(docs)}")
        notes.append(f"Forms detected in tender pack: {len(detected_forms)}")
        notes.append(f"Required forms identified: {len(required_forms)}")
        notes.append(f"Missing required forms needing fallback/manual review: {len(missing_forms)}")
        return notes


# -----------------------------------------------------------------------------
# Convenience functions
# -----------------------------------------------------------------------------

def build_tender_submission_plan(
    tender_root: str,
    tender_id: Optional[str] = None,
    instructions_text: Optional[str] = None,
    mandatory_form_codes: Optional[List[str]] = None,
    enable_archive_extract: bool = True,
) -> Dict[str, Any]:
    engine = TenderFormPriorityEngine()
    return engine.build_submission_plan(
        tender_root=tender_root,
        tender_id=tender_id,
        instructions_text=instructions_text,
        mandatory_form_codes=mandatory_form_codes or [],
        enable_archive_extract=enable_archive_extract,
    )


def save_tender_submission_plan(
    output_path: str,
    tender_root: str,
    tender_id: Optional[str] = None,
    instructions_text: Optional[str] = None,
    mandatory_form_codes: Optional[List[str]] = None,
    enable_archive_extract: bool = True,
) -> str:
    plan = build_tender_submission_plan(
        tender_root=tender_root,
        tender_id=tender_id,
        instructions_text=instructions_text,
        mandatory_form_codes=mandatory_form_codes or [],
        enable_archive_extract=enable_archive_extract,
    )
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return str(out)
