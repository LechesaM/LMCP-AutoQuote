from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.auto_profile_generator import AutoProfileGenerator
from app.services.sbd_auto_detection_engine import SBDAutoDetectionEngine
from app.services.tender_submission_pipeline import TenderSubmissionPipeline


class AutoMultiFormPipelineError(Exception):
    pass


class AutoMultiFormPipeline:
    """
    Full auto multi-form orchestration layer.

    Purpose:
    - scan a tender root for PDFs
    - detect all likely form families per PDF
    - auto-generate missing starter profiles for each detected form
    - build a profile override map for the submission pipeline
    - run TenderSubmissionPipeline with those generated profiles
    """

    def __init__(
        self,
        profile_dir: str = "app/data/form_profiles",
        submission_pipeline: Optional[TenderSubmissionPipeline] = None,
        profile_generator: Optional[AutoProfileGenerator] = None,
    ) -> None:
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        self.submission_pipeline = submission_pipeline or TenderSubmissionPipeline()
        self.profile_generator = profile_generator or AutoProfileGenerator(profile_dir=str(self.profile_dir))

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
        witness_1_signature_path: Optional[str] = None,
        witness_2_signature_path: Optional[str] = None,
        enable_archive_extract: bool = True,
        overwrite_existing_generated_profiles: bool = False,
    ) -> Dict[str, Any]:
        tender_root_path = Path(tender_root)
        if not tender_root_path.exists():
            raise AutoMultiFormPipelineError(f"Tender root not found: {tender_root}")

        pdf_files = self._find_pdf_files(tender_root_path)
        if not pdf_files:
            raise AutoMultiFormPipelineError(f"No PDF files found inside: {tender_root}")

        generated_profiles_summary: List[Dict[str, Any]] = []
        profile_override_map: Dict[str, str] = {}

        for pdf_path in pdf_files:
            result = self._generate_all_profiles_from_pdf(
                input_pdf_path=str(pdf_path),
                overwrite_existing=overwrite_existing_generated_profiles,
            )
            generated_profiles_summary.append(result)

            for mapping in result.get("form_profile_map", []):
                form_code = mapping.get("form_code")
                profile_name = mapping.get("profile_name")
                if form_code and profile_name and form_code not in profile_override_map:
                    profile_override_map[form_code] = profile_name

        submission_result = self.submission_pipeline.run(
            tender_root=str(tender_root_path),
            tender_id=tender_id,
            instructions_text=instructions_text,
            mandatory_form_codes=mandatory_form_codes,
            company_data=company_data,
            director_data=director_data,
            tender_data=tender_data,
            signature_path=signature_path,
            witness_1_signature_path=witness_1_signature_path,
            witness_2_signature_path=witness_2_signature_path,
            form_profile_map=profile_override_map,
            enable_archive_extract=enable_archive_extract,
        )

        submission_result["auto_multi_form"] = {
            "status": "success",
            "pdfs_scanned": [str(p) for p in pdf_files],
            "generated_profiles_summary": generated_profiles_summary,
            "profile_override_map": profile_override_map,
            "signature_inputs": {
                "signature_path": signature_path,
                "witness_1_signature_path": witness_1_signature_path,
                "witness_2_signature_path": witness_2_signature_path,
            },
        }

        return submission_result

    # ------------------------------------------------------------------
    # PDF scanning
    # ------------------------------------------------------------------

    def _find_pdf_files(self, tender_root_path: Path) -> List[Path]:
        results: List[Path] = []
        for path in tender_root_path.rglob("*.pdf"):
            if path.is_file():
                results.append(path)
        return sorted(results)

    # ------------------------------------------------------------------
    # Multi-profile generation per PDF
    # ------------------------------------------------------------------

    def _generate_all_profiles_from_pdf(
        self,
        input_pdf_path: str,
        overwrite_existing: bool = False,
    ) -> Dict[str, Any]:
        pdf_path = Path(input_pdf_path)
        detections = SBDAutoDetectionEngine.detect_pdf(str(pdf_path))

        created_profiles: List[str] = []
        form_profile_map: List[Dict[str, str]] = []
        skipped_profiles: List[Dict[str, Any]] = []

        seen_output_names = set()

        for detection in detections:
            profile_template = detection.suggested_profile
            if not profile_template:
                skipped_profiles.append(
                    {
                        "form_code": detection.form_code,
                        "page_index": detection.page_index,
                        "reason": "No suggested profile returned by detector",
                    }
                )
                continue

            if profile_template not in self.profile_generator.BASE_PROFILES:
                skipped_profiles.append(
                    {
                        "form_code": detection.form_code,
                        "page_index": detection.page_index,
                        "reason": f"Starter profile template not found: {profile_template}",
                    }
                )
                continue

            output_filename = self._build_profile_filename(
                pdf_stem=pdf_path.stem,
                form_code=detection.form_code,
                profile_template=profile_template,
            )

            if output_filename in seen_output_names:
                continue
            seen_output_names.add(output_filename)

            output_path = self.profile_dir / output_filename

            if output_path.exists() and not overwrite_existing:
                created_profiles.append(str(output_path))
                form_profile_map.append(
                    {
                        "form_code": detection.form_code,
                        "profile_name": output_filename,
                    }
                )
                continue

            profile = self._build_profile_from_detection(
                profile_template=profile_template,
                output_filename=output_filename,
                page_index=detection.page_index or 0,
            )

            output_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")

            created_profiles.append(str(output_path))
            form_profile_map.append(
                {
                    "form_code": detection.form_code,
                    "profile_name": output_filename,
                }
            )

        return {
            "input_pdf_path": str(pdf_path),
            "detections": [
                {
                    "form_code": d.form_code,
                    "confidence": d.confidence,
                    "buyer_family": d.buyer_family,
                    "stamp_allowed": d.stamp_allowed,
                    "witness_required": d.witness_required,
                    "suggested_profile": d.suggested_profile,
                    "page_index": d.page_index,
                }
                for d in detections
            ],
            "created_profiles": created_profiles,
            "form_profile_map": form_profile_map,
            "skipped_profiles": skipped_profiles,
        }

    def _build_profile_from_detection(
        self,
        profile_template: str,
        output_filename: str,
        page_index: int,
    ) -> Dict[str, Any]:
        starter = json.loads(json.dumps(self.profile_generator.BASE_PROFILES[profile_template]))

        self.profile_generator._apply_page_index_to_signature_coordinates(starter, page_index)
        self.profile_generator._apply_page_index_to_anchor_rules(starter, page_index)
        starter["name"] = Path(output_filename).stem

        return starter

    def _build_profile_filename(
        self,
        pdf_stem: str,
        form_code: str,
        profile_template: str,
    ) -> str:
        safe_pdf_stem = self._sanitize_filename_part(pdf_stem, "TENDER")
        safe_form_code = self._sanitize_filename_part(form_code, "form")
        safe_template = self._sanitize_filename_part(Path(profile_template).stem, "profile")
        return f"{safe_pdf_stem}__{safe_form_code}__{safe_template}.json"

    @staticmethod
    def _sanitize_filename_part(value: str, default: str = "profile") -> str:
        import re

        text = str(value or "").strip()
        text = re.sub(r"[^\w\-.]+", "_", text)
        text = text.strip("._")
        return text or default


if __name__ == "__main__":
    pipeline = AutoMultiFormPipeline()

    result = pipeline.run(
        tender_root="runtime/test_tender_pack",
        tender_id="AUTO_MULTI_FORM_TEST",
    )

    print(json.dumps(result, indent=2))

