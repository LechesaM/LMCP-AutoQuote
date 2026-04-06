import json
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.sbd_version_detector import SBDVersionDetector
from app.services.tender_form_priority_engine import build_tender_submission_plan
from app.services.universal_form_filler import (
    UniversalFormFiller,
    UniversalFormFillerError,
    build_lmcp_default_form_data,
)


@dataclass
class FilledDocumentResult:
    source_path: str
    output_path: Optional[str]
    output_pdf_path: Optional[str]
    form_code: Optional[str]
    status: str
    reason: str
    source: str


@dataclass
class GeneratedFallbackResult:
    form_code: str
    template_path: Optional[str]
    output_path: Optional[str]
    output_pdf_path: Optional[str]
    status: str
    reason: str


class TenderSubmissionPipeline:
    """
    Full no-duplicate tender submission pipeline.

    Flow:
    1. Scan tender pack
    2. Detect and prioritise forms already inside the tender pack
    3. Fill those exact forms first
    4. Generate only missing required fallback forms
    5. Copy/collect supporting documents
    6. Build one clean final submission folder

    Version-aware routing:
    - SBD4 old -> sbd4_old_profile.json
    - SBD4 new -> sbd4_new_profile.json
    """

    def __init__(
        self,
        output_root: str = "runtime/submissions",
        generated_forms_root: str = "runtime/generated_forms",
        filler: Optional[UniversalFormFiller] = None,
    ) -> None:
        self.output_root = Path(output_root)
        self.generated_forms_root = Path(generated_forms_root)
        self.filler = filler or UniversalFormFiller(output_dir=str(self.generated_forms_root))
        self.sbd_version_detector = SBDVersionDetector()

        self.output_root.mkdir(parents=True, exist_ok=True)
        self.generated_forms_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(
        self,
        tender_root: str,
        tender_id: Optional[str] = None,
        instructions_text: Optional[str] = None,
        mandatory_form_codes: Optional[List[str]] = None,
        company_data: Optional[Dict[str, Any]] = None,
        director_data: Optional[Dict[str, Any]] = None,
        tender_data: Optional[Dict[str, Any]] = None,
        signature_path: Optional[str] = None,
        form_profile_map: Optional[Dict[str, str]] = None,
        enable_archive_extract: bool = True,
    ) -> Dict[str, Any]:
        tender_id = tender_id or "TENDER_SUBMISSION"
        safe_tender_id = self._sanitize_name(tender_id)

        submission_dir = self.output_root / safe_tender_id
        filled_dir = submission_dir / "filled_forms"
        supporting_dir = submission_dir / "supporting_documents"
        plan_dir = submission_dir / "plan"

        filled_dir.mkdir(parents=True, exist_ok=True)
        supporting_dir.mkdir(parents=True, exist_ok=True)
        plan_dir.mkdir(parents=True, exist_ok=True)

        merged_data = build_lmcp_default_form_data(
            tender_data=tender_data or {},
            company_data=company_data or {},
            director_data=director_data or {},
        )

        plan = build_tender_submission_plan(
            tender_root=tender_root,
            tender_id=tender_id,
            instructions_text=instructions_text,
            mandatory_form_codes=mandatory_form_codes or [],
            enable_archive_extract=enable_archive_extract,
        )

        plan_path = plan_dir / "tender_submission_plan.json"
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

        selected_submission_documents = plan.get("selected_submission_documents", [])
        generated_fallback_requests = plan.get("generated_fallback_requests", [])

        filled_existing_results = self._fill_existing_priority_documents(
            selected_submission_documents=selected_submission_documents,
            merged_data=merged_data,
            signature_path=signature_path,
            form_profile_map=form_profile_map or {},
            filled_dir=filled_dir,
            supporting_dir=supporting_dir,
        )

        generated_fallback_results = self._generate_missing_fallback_forms(
            generated_fallback_requests=generated_fallback_requests,
            merged_data=merged_data,
            signature_path=signature_path,
            form_profile_map=form_profile_map or {},
            filled_dir=filled_dir,
        )

        manifest = self._build_manifest(
            tender_id=tender_id,
            tender_root=tender_root,
            plan=plan,
            filled_existing_results=filled_existing_results,
            generated_fallback_results=generated_fallback_results,
            submission_dir=submission_dir,
        )

        manifest_path = submission_dir / "submission_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return manifest

    # ------------------------------------------------------------------
    # Existing tender-pack forms first
    # ------------------------------------------------------------------

    def _fill_existing_priority_documents(
        self,
        selected_submission_documents: List[Dict[str, Any]],
        merged_data: Dict[str, Any],
        signature_path: Optional[str],
        form_profile_map: Dict[str, str],
        filled_dir: Path,
        supporting_dir: Path,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for doc in selected_submission_documents:
            source_path = doc.get("path")
            form_code = doc.get("form_code")
            filename = doc.get("filename", Path(source_path).name if source_path else "unknown")
            source = doc.get("source", "tender_pack")

            if not source_path or not Path(source_path).exists():
                results.append(
                    asdict(
                        FilledDocumentResult(
                            source_path=source_path or "",
                            output_path=None,
                            output_pdf_path=None,
                            form_code=form_code,
                            status="missing_source",
                            reason="Selected document path does not exist",
                            source=source,
                        )
                    )
                )
                continue

            ext = Path(source_path).suffix.lower()

            if form_code:
                profile_name = self._resolve_profile_name(
                    source_path=source_path,
                    form_code=form_code,
                    form_profile_map=form_profile_map,
                )

                output_basename = self._basename_for_output(form_code, filename)

                try:
                    fill_result = self.filler.fill_form(
                        input_path=source_path,
                        data=merged_data,
                        output_basename=output_basename,
                        profile_name=profile_name,
                        signature_path=signature_path,
                        convert_to_pdf=True,
                    )

                    copied_result = self._copy_fill_output_into_submission(
                        fill_result=fill_result,
                        destination_dir=filled_dir,
                    )

                    results.append(
                        asdict(
                            FilledDocumentResult(
                                source_path=source_path,
                                output_path=copied_result.get("output_path"),
                                output_pdf_path=copied_result.get("output_pdf_path"),
                                form_code=form_code,
                                status="filled",
                                reason=(
                                    f"Existing tender-pack form filled successfully"
                                    + (f" using profile '{profile_name}'" if profile_name else "")
                                ),
                                source=source,
                            )
                        )
                    )
                except UniversalFormFillerError as exc:
                    copied_source = self._copy_file(source_path, supporting_dir / Path(source_path).name)
                    results.append(
                        asdict(
                            FilledDocumentResult(
                                source_path=source_path,
                                output_path=str(copied_source),
                                output_pdf_path=str(copied_source) if ext == ".pdf" else None,
                                form_code=form_code,
                                status="manual_review_required",
                                reason=f"Existing form detected but could not be auto-filled: {str(exc)}",
                                source=source,
                            )
                        )
                    )
                except Exception as exc:
                    copied_source = self._copy_file(source_path, supporting_dir / Path(source_path).name)
                    results.append(
                        asdict(
                            FilledDocumentResult(
                                source_path=source_path,
                                output_path=str(copied_source),
                                output_pdf_path=str(copied_source) if ext == ".pdf" else None,
                                form_code=form_code,
                                status="manual_review_required",
                                reason=f"Unexpected fill error: {str(exc)}",
                                source=source,
                            )
                        )
                    )
            else:
                copied_source = self._copy_file(source_path, supporting_dir / Path(source_path).name)
                results.append(
                    asdict(
                        FilledDocumentResult(
                            source_path=source_path,
                            output_path=str(copied_source),
                            output_pdf_path=str(copied_source) if ext == ".pdf" else None,
                            form_code=None,
                            status="copied_supporting_document",
                            reason="Supporting document copied to submission set",
                            source=source,
                        )
                    )
                )

        return results

    # ------------------------------------------------------------------
    # Generate only missing fallback forms
    # ------------------------------------------------------------------

    def _generate_missing_fallback_forms(
        self,
        generated_fallback_requests: List[Dict[str, Any]],
        merged_data: Dict[str, Any],
        signature_path: Optional[str],
        form_profile_map: Dict[str, str],
        filled_dir: Path,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for item in generated_fallback_requests:
            form_code = item.get("form_code")
            template_path = item.get("template_path")
            action = item.get("action")
            reason = item.get("reason", "")

            if action == "manual_review_required":
                results.append(
                    asdict(
                        GeneratedFallbackResult(
                            form_code=form_code or "",
                            template_path=template_path,
                            output_path=None,
                            output_pdf_path=None,
                            status="manual_review_required",
                            reason=reason,
                        )
                    )
                )
                continue

            if not template_path or not Path(template_path).exists():
                results.append(
                    asdict(
                        GeneratedFallbackResult(
                            form_code=form_code or "",
                            template_path=template_path,
                            output_path=None,
                            output_pdf_path=None,
                            status="manual_review_required",
                            reason=f"Fallback template missing. {reason}",
                        )
                    )
                )
                continue

            profile_name = self._resolve_profile_name(
                source_path=template_path,
                form_code=form_code or "",
                form_profile_map=form_profile_map,
            )

            output_basename = f"FALLBACK_{self._sanitize_name(form_code or 'FORM')}"

            try:
                fill_result = self.filler.fill_form(
                    input_path=template_path,
                    data=merged_data,
                    output_basename=output_basename,
                    profile_name=profile_name,
                    signature_path=signature_path,
                    convert_to_pdf=True,
                )

                copied_result = self._copy_fill_output_into_submission(
                    fill_result=fill_result,
                    destination_dir=filled_dir,
                )

                results.append(
                    asdict(
                        GeneratedFallbackResult(
                            form_code=form_code or "",
                            template_path=template_path,
                            output_path=copied_result.get("output_path"),
                            output_pdf_path=copied_result.get("output_pdf_path"),
                            status="generated",
                            reason=(
                                f"Fallback form generated because required form was missing. {reason}"
                                + (f" Profile used: {profile_name}" if profile_name else "")
                            ),
                        )
                    )
                )
            except Exception as exc:
                results.append(
                    asdict(
                        GeneratedFallbackResult(
                            form_code=form_code or "",
                            template_path=template_path,
                            output_path=None,
                            output_pdf_path=None,
                            status="manual_review_required",
                            reason=f"Fallback generation failed: {str(exc)}",
                        )
                    )
                )

        return results

    # ------------------------------------------------------------------
    # Profile routing
    # ------------------------------------------------------------------

    def _resolve_profile_name(
        self,
        source_path: str,
        form_code: str,
        form_profile_map: Dict[str, str],
    ) -> Optional[str]:
        profile_name = form_profile_map.get(form_code)

        if form_code == "sbd4":
            try:
                version_result = self.sbd_version_detector.detect_file(source_path)
                detected_version = version_result.get("detected_version")
                detected_profile = version_result.get("profile_name")

                if detected_version == "new" and detected_profile:
                    return detected_profile
                if detected_version == "old" and detected_profile:
                    return detected_profile
            except Exception:
                pass

        return profile_name

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------

    def _build_manifest(
        self,
        tender_id: str,
        tender_root: str,
        plan: Dict[str, Any],
        filled_existing_results: List[Dict[str, Any]],
        generated_fallback_results: List[Dict[str, Any]],
        submission_dir: Path,
    ) -> Dict[str, Any]:
        final_files = []
        for path in submission_dir.rglob("*"):
            if path.is_file():
                final_files.append(str(path))

        return {
            "status": "success",
            "tender_id": tender_id,
            "tender_root": tender_root,
            "submission_dir": str(submission_dir),
            "policy": (
                "Prioritise completing forms already contained in the RFQ/tender pack. "
                "Do not generate duplicate standalone SBD forms when the same forms already "
                "exist in the tender pack. Generate fallback forms only when required forms "
                "are missing, unreadable, or explicitly needed separately."
            ),
            "plan_summary": {
                "documents_found": len(plan.get("documents_found", [])),
                "detected_forms": len(plan.get("detected_forms", [])),
                "required_forms": len(plan.get("required_forms", [])),
                "missing_forms": len(plan.get("missing_forms", [])),
                "selected_submission_documents": len(plan.get("selected_submission_documents", [])),
                "fallback_requests": len(plan.get("generated_fallback_requests", [])),
            },
            "filled_existing_results": filled_existing_results,
            "generated_fallback_results": generated_fallback_results,
            "skipped_duplicates": plan.get("skipped_duplicates", []),
            "notes": plan.get("notes", []),
            "final_files": sorted(final_files),
        }

    # ------------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------------

    def _copy_fill_output_into_submission(
        self,
        fill_result: Dict[str, Any],
        destination_dir: Path,
    ) -> Dict[str, Optional[str]]:
        output_path = fill_result.get("output_path")
        output_pdf_path = fill_result.get("output_pdf_path")

        copied_output_path = None
        copied_output_pdf_path = None

        if output_path and Path(output_path).exists():
            dest = destination_dir / Path(output_path).name
            self._copy_file(output_path, dest)
            copied_output_path = str(dest)

        if output_pdf_path and Path(output_pdf_path).exists():
            dest_pdf = destination_dir / Path(output_pdf_path).name
            self._copy_file(output_pdf_path, dest_pdf)
            copied_output_pdf_path = str(dest_pdf)

        return {
            "output_path": copied_output_path,
            "output_pdf_path": copied_output_pdf_path,
        }

    def _copy_file(self, src: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return dest

    def _basename_for_output(self, form_code: str, filename: str) -> str:
        stem = Path(filename).stem
        return f"{self._sanitize_name(form_code)}__{self._sanitize_name(stem)}__COMPLETED"

    def _sanitize_name(self, value: str) -> str:
        value = value.strip().replace(" ", "_")
        safe = "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in value)
        while "__" in safe:
            safe = safe.replace("__", "_")
        return safe[:180]
