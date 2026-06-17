from __future__ import annotations

import importlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.services.tender_pipeline_models import (
    DocumentType,
    EligibilityDecision,
    NormalizedTender,
    TenderStatus,
)

logger = logging.getLogger(__name__)


class TenderQuotePackGenerator:
    """
    Integration layer between the tender pipeline and your real generators.

    What it does:
    1. Creates a tender output folder
    2. Writes a tender summary JSON
    3. Builds a pricing schedule shell (.xlsx) if openpyxl is available
    4. Tries to call a real SBD generator if one exists in your project
    5. Tries to call a real PDF merge/submission pack generator if one exists
    6. Falls back safely without crashing the pipeline
    """

    def __init__(
        self,
        *,
        base_output_dir: str | None = None,
    ) -> None:
        if base_output_dir is None:
            base_output_dir = str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "generated_tenders")
        self.base_output_dir = Path(base_output_dir)
        self.base_output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def generate_for_tender(self, tender: NormalizedTender) -> NormalizedTender:
        if tender.eligibility.decision != EligibilityDecision.ELIGIBLE:
            tender.add_note("Quote pack generation skipped because tender is not eligible.")
            tender.add_tag("quote_pack_skipped")
            return tender

        output_dir = self._get_output_dir(tender)
        output_dir.mkdir(parents=True, exist_ok=True)

        generated_files: Dict[str, Optional[str]] = {
            "summary_json": None,
            "pricing_schedule_xlsx": None,
            "sbd_pack_pdf": None,
            "submission_pack_pdf": None,
            "pack_manifest_json": None,
        }

        # 1. Summary JSON
        summary_path = self._write_summary_json(tender, output_dir)
        generated_files["summary_json"] = str(summary_path)
        tender.add_artifact(
            artifact_type="tender_summary",
            file_name=summary_path.name,
            local_path=str(summary_path),
            metadata={"generated_by": "TenderQuotePackGenerator"},
        )

        # 2. Pricing schedule shell
        pricing_path = self._write_pricing_schedule_shell(tender, output_dir)
        if pricing_path:
            generated_files["pricing_schedule_xlsx"] = str(pricing_path)
            tender.add_artifact(
                artifact_type="pricing_schedule",
                file_name=pricing_path.name,
                local_path=str(pricing_path),
                metadata={"generated_by": "TenderQuotePackGenerator"},
            )

        # 3. SBD pack
        sbd_pack_path = self._generate_real_or_fallback_sbd_pack(tender, output_dir)
        if sbd_pack_path:
            generated_files["sbd_pack_pdf"] = str(sbd_pack_path)
            tender.add_artifact(
                artifact_type="sbd_pack",
                file_name=sbd_pack_path.name,
                local_path=str(sbd_pack_path),
                metadata={"generated_by": "TenderQuotePackGenerator"},
            )

        # 4. Submission pack
        submission_pack_path = self._generate_real_or_fallback_submission_pack(
            tender=tender,
            output_dir=output_dir,
            pricing_path=pricing_path,
            sbd_pack_path=sbd_pack_path,
            summary_path=summary_path,
        )
        if submission_pack_path:
            generated_files["submission_pack_pdf"] = str(submission_pack_path)
            tender.add_artifact(
                artifact_type="submission_pack",
                file_name=submission_pack_path.name,
                local_path=str(submission_pack_path),
                metadata={"generated_by": "TenderQuotePackGenerator"},
            )

        # 5. Manifest
        manifest_path = self._write_pack_manifest(
            tender=tender,
            output_dir=output_dir,
            generated_files=generated_files,
        )
        generated_files["pack_manifest_json"] = str(manifest_path)
        tender.add_artifact(
            artifact_type="pack_manifest",
            file_name=manifest_path.name,
            local_path=str(manifest_path),
            metadata={"generated_by": "TenderQuotePackGenerator"},
        )

        # Final status
        if submission_pack_path:
            tender.status = TenderStatus.PACK_GENERATED
            tender.add_note("Submission pack generated successfully.")
            tender.add_tag("submission_pack_generated")
        else:
            tender.status = TenderStatus.QUOTE_GENERATED
            tender.add_note("Partial quote pack generated. Submission pack PDF still needs final integration.")
            tender.add_tag("partial_quote_pack_generated")

        return tender

    # ------------------------------------------------------------------
    # Output paths
    # ------------------------------------------------------------------
    def _get_output_dir(self, tender: NormalizedTender) -> Path:
        safe_ref = self._slugify(tender.reference_number or "no-reference")
        safe_title = self._slugify(tender.title)[:80]
        safe_entity = self._slugify(tender.issuing_entity)[:60]
        folder_name = f"{tender.tender_id}_{safe_ref}_{safe_entity}_{safe_title}"
        return self.base_output_dir / folder_name

    # ------------------------------------------------------------------
    # Summary JSON
    # ------------------------------------------------------------------
    def _write_summary_json(self, tender: NormalizedTender, output_dir: Path) -> Path:
        summary_path = output_dir / f"{tender.tender_id}_tender_summary.json"

        payload = {
            "generated_at": datetime.utcnow().isoformat(),
            "tender_id": tender.tender_id,
            "reference_number": tender.reference_number,
            "title": tender.title,
            "issuing_entity": tender.issuing_entity,
            "source": tender.source,
            "source_type": tender.source_type,
            "source_url": tender.source_url,
            "notice_url": tender.notice_url,
            "harvested_at": tender.harvested_at.isoformat() if tender.harvested_at else None,
            "published_at": tender.published_at.isoformat() if tender.published_at else None,
            "closing_at": tender.closing_at.isoformat() if tender.closing_at else None,
            "submission_method": tender.submission_method.value,
            "submission_email": tender.submission_email,
            "submission_address": tender.submission_address,
            "portal_name": tender.portal_name,
            "portal_url": tender.portal_url,
            "briefing_requirement": tender.briefing_requirement.value,
            "briefing_location": tender.briefing_location,
            "description": tender.description,
            "scope_summary": tender.scope_summary,
            "category": tender.category,
            "subcategory": tender.subcategory,
            "region": tender.region,
            "province": tender.province,
            "municipality": tender.municipality,
            "estimated_value": tender.estimated_value,
            "currency": tender.currency,
            "cidb_grading": tender.cidb_grading,
            "status": tender.status.value,
            "eligibility_decision": tender.eligibility.decision.value,
            "eligibility_reasons": tender.eligibility.reasons,
            "score": tender.scoring.score,
            "priority_band": tender.scoring.priority_band,
            "sector_fit": tender.scoring.sector_fit,
            "estimated_value_band": tender.scoring.estimated_value_band,
            "documents": [
                {
                    "name": d.name,
                    "url": d.url,
                    "document_type": d.document_type.value,
                    "file_name": d.file_name,
                    "file_extension": d.file_extension,
                    "local_path": d.local_path,
                    "size_bytes": d.size_bytes,
                }
                for d in tender.documents
            ],
            "contacts": [
                {
                    "name": c.name,
                    "email": c.email,
                    "phone": c.phone,
                    "department": c.department,
                }
                for c in tender.contact_details
            ],
            "tags": tender.tags,
            "notes": tender.notes,
        }

        summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return summary_path

    # ------------------------------------------------------------------
    # Pricing schedule shell
    # ------------------------------------------------------------------
    def _write_pricing_schedule_shell(self, tender: NormalizedTender, output_dir: Path) -> Optional[Path]:
        try:
            from openpyxl import Workbook
        except Exception as exc:
            logger.warning("openpyxl unavailable; pricing shell not created: %s", exc)
            tender.add_note("Pricing schedule shell was skipped because openpyxl is unavailable.")
            return None

        file_path = output_dir / f"{tender.tender_id}_pricing_schedule.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "Pricing Schedule"

        rows = [
            ["LMCP Tender Pricing Schedule"],
            [],
            ["Tender ID", tender.tender_id],
            ["Reference Number", tender.reference_number or ""],
            ["Tender Title", tender.title],
            ["Issuing Entity", tender.issuing_entity],
            ["Closing Date", tender.closing_at.isoformat() if tender.closing_at else ""],
            ["Submission Method", tender.submission_method.value],
            ["Submission Email", tender.submission_email or ""],
            ["Portal", tender.portal_name or ""],
            ["Province", tender.province or ""],
            ["Municipality", tender.municipality or ""],
            ["Estimated Value", tender.estimated_value if tender.estimated_value is not None else ""],
            ["CIDB Grading", tender.cidb_grading or ""],
            [],
            ["BoQ / Pricing Input"],
            ["Item No", "Description", "Unit", "Qty", "Rate (ZAR)", "Amount (ZAR)"],
            [1, "Pricing item 1", "", "", "", "=D18*E18"],
            [2, "Pricing item 2", "", "", "", "=D19*E19"],
            [3, "Pricing item 3", "", "", "", "=D20*E20"],
            [],
            ["Subtotal", "", "", "", "", "=SUM(F18:F20)"],
            ["VAT (15%)", "", "", "", "", "=F22*15%"],
            ["Total Incl. VAT", "", "", "", "", "=F22+F23"],
        ]

        for row in rows:
            ws.append(row)

        ws.column_dimensions["A"].width = 18
        ws.column_dimensions["B"].width = 50
        ws.column_dimensions["C"].width = 12
        ws.column_dimensions["D"].width = 12
        ws.column_dimensions["E"].width = 15
        ws.column_dimensions["F"].width = 18

        wb.save(file_path)
        tender.add_note("Pricing schedule shell generated.")
        return file_path

    # ------------------------------------------------------------------
    # SBD pack generation
    # ------------------------------------------------------------------
    def _generate_real_or_fallback_sbd_pack(
        self,
        tender: NormalizedTender,
        output_dir: Path,
    ) -> Optional[Path]:
        output_pdf = output_dir / f"{tender.tender_id}_sbd_pack.pdf"

        # Try real project integrations first
        sbd_call_candidates: List[Tuple[str, str]] = [
            ("app.sbd_generator", "generate_sbd_pack"),
            ("app.services.sbd_generator", "generate_sbd_pack"),
            ("app.sbd_generator", "generate_sbd_pdf"),
            ("app.services.sbd_generator", "generate_sbd_pdf"),
            ("app.services.submission_pack", "generate_sbd_pack"),
        ]

        for module_name, func_name in sbd_call_candidates:
            result = self._call_optional_function(
                module_name=module_name,
                func_name=func_name,
                tender=tender,
                output_path=str(output_pdf),
                output_dir=str(output_dir),
            )
            if result:
                final_path = self._normalize_returned_path(result, fallback=str(output_pdf))
                if final_path and Path(final_path).exists():
                    tender.add_note(f"Real SBD generator executed via {module_name}.{func_name}.")
                    return Path(final_path)

        # Fallback: create a placeholder SBD manifest PDF-like text file if no real generator exists
        placeholder_path = output_dir / f"{tender.tender_id}_sbd_pack_placeholder.pdf"
        content = self._build_sbd_placeholder_text(tender)
        placeholder_path.write_text(content, encoding="utf-8")

        tender.add_note("No real SBD generator was found. Placeholder SBD pack file created.")
        tender.add_tag("sbd_placeholder")
        return placeholder_path

    # ------------------------------------------------------------------
    # Submission pack generation
    # ------------------------------------------------------------------
    def _generate_real_or_fallback_submission_pack(
        self,
        *,
        tender: NormalizedTender,
        output_dir: Path,
        pricing_path: Optional[Path],
        sbd_pack_path: Optional[Path],
        summary_path: Path,
    ) -> Optional[Path]:
        output_pdf = output_dir / f"{tender.tender_id}_submission_pack.pdf"

        # Candidate attachments / pack items
        candidate_paths: List[str] = []
        for p in [str(summary_path), str(pricing_path) if pricing_path else None, str(sbd_pack_path) if sbd_pack_path else None]:
            if p:
                candidate_paths.append(p)

        # First try a real submission pack builder
        pack_call_candidates: List[Tuple[str, str]] = [
            ("app.services.submission_pack", "generate_submission_pack"),
            ("app.submission_pack", "generate_submission_pack"),
            ("app.services.pdf_generator", "generate_submission_pack"),
            ("app.services.pdf_generator", "merge_pdfs"),
            ("app.pdf_generator", "merge_pdfs"),
        ]

        for module_name, func_name in pack_call_candidates:
            result = self._call_optional_function(
                module_name=module_name,
                func_name=func_name,
                tender=tender,
                output_path=str(output_pdf),
                output_dir=str(output_dir),
                input_files=candidate_paths,
            )
            if result:
                final_path = self._normalize_returned_path(result, fallback=str(output_pdf))
                if final_path and Path(final_path).exists():
                    tender.add_note(f"Real submission pack generator executed via {module_name}.{func_name}.")
                    return Path(final_path)

        # Fallback: create a pack manifest with .pdf extension so the pipeline still has a concrete artifact
        placeholder_path = output_dir / f"{tender.tender_id}_submission_pack_placeholder.pdf"
        placeholder_text = self._build_submission_pack_placeholder_text(
            tender=tender,
            candidate_paths=candidate_paths,
        )
        placeholder_path.write_text(placeholder_text, encoding="utf-8")

        tender.add_note("No real submission pack PDF merger was found. Placeholder submission pack file created.")
        tender.add_tag("submission_pack_placeholder")
        return placeholder_path

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------
    def _write_pack_manifest(
        self,
        *,
        tender: NormalizedTender,
        output_dir: Path,
        generated_files: Dict[str, Optional[str]],
    ) -> Path:
        manifest_path = output_dir / f"{tender.tender_id}_pack_manifest.json"

        payload = {
            "generated_at": datetime.utcnow().isoformat(),
            "tender_id": tender.tender_id,
            "title": tender.title,
            "issuing_entity": tender.issuing_entity,
            "reference_number": tender.reference_number,
            "eligibility_decision": tender.eligibility.decision.value,
            "status": tender.status.value,
            "generated_files": generated_files,
            "document_inventory": [
                {
                    "name": doc.name,
                    "document_type": doc.document_type.value,
                    "url": doc.url,
                    "local_path": doc.local_path,
                }
                for doc in tender.documents
            ],
            "notes": tender.notes,
            "tags": tender.tags,
        }

        manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return manifest_path

    # ------------------------------------------------------------------
    # Optional project function calls
    # ------------------------------------------------------------------
    def _call_optional_function(
        self,
        *,
        module_name: str,
        func_name: str,
        tender: NormalizedTender,
        output_path: str,
        output_dir: str,
        input_files: Optional[List[str]] = None,
    ) -> Any:
        try:
            module = importlib.import_module(module_name)
        except Exception:
            return None

        func = getattr(module, func_name, None)
        if not callable(func):
            return None

        # Try progressively more generic signatures so this adapts to your existing project
        call_attempts = [
            lambda: func(tender=tender, output_path=output_path, output_dir=output_dir, input_files=input_files),
            lambda: func(tender=tender, output_path=output_path, output_dir=output_dir),
            lambda: func(tender=tender, output_path=output_path),
            lambda: func(tender=tender, output_dir=output_dir),
            lambda: func(tender=tender),
            lambda: func(output_path=output_path, input_files=input_files),
            lambda: func(output_path=output_path),
        ]

        for attempt in call_attempts:
            try:
                result = attempt()
                logger.info("Executed optional function %s.%s successfully.", module_name, func_name)
                return result
            except TypeError:
                continue
            except Exception as exc:
                logger.exception("Optional function %s.%s failed: %s", module_name, func_name, exc)
                return None

        return None

    @staticmethod
    def _normalize_returned_path(result: Any, fallback: Optional[str] = None) -> Optional[str]:
        if result is None:
            return fallback
        if isinstance(result, str):
            return result
        if isinstance(result, Path):
            return str(result)
        if isinstance(result, dict):
            for key in ["output_path", "path", "file_path", "pdf_path", "local_path"]:
                value = result.get(key)
                if value:
                    return str(value)
        return fallback

    # ------------------------------------------------------------------
    # Placeholders
    # ------------------------------------------------------------------
    def _build_sbd_placeholder_text(self, tender: NormalizedTender) -> str:
        return "\n".join(
            [
                "LMCP SBD PACK PLACEHOLDER",
                f"Generated At: {datetime.utcnow().isoformat()}",
                f"Tender ID: {tender.tender_id}",
                f"Reference Number: {tender.reference_number or ''}",
                f"Tender Title: {tender.title}",
                f"Issuing Entity: {tender.issuing_entity}",
                "",
                "Expected SBD contents to integrate from real generator:",
                "- SBD 1",
                "- SBD 4",
                "- SBD 6.1 / pricing declarations where applicable",
                "- Declaration pages",
                "- Embedded signature where configured",
                "",
                "This placeholder exists because no compatible SBD generator function was found automatically.",
            ]
        )

    def _build_submission_pack_placeholder_text(
        self,
        *,
        tender: NormalizedTender,
        candidate_paths: List[str],
    ) -> str:
        lines = [
            "LMCP SUBMISSION PACK PLACEHOLDER",
            f"Generated At: {datetime.utcnow().isoformat()}",
            f"Tender ID: {tender.tender_id}",
            f"Reference Number: {tender.reference_number or ''}",
            f"Tender Title: {tender.title}",
            f"Issuing Entity: {tender.issuing_entity}",
            "",
            "Pack items that should be merged into the final PDF:",
        ]
        for item in candidate_paths:
            lines.append(f"- {item}")

        lines.extend(
            [
                "",
                "This placeholder exists because no compatible PDF merge / submission pack generator was found automatically.",
            ]
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    @staticmethod
    def _slugify(value: str) -> str:
        value = (value or "").strip().lower()
        cleaned = []
        for ch in value:
            if ch.isalnum():
                cleaned.append(ch)
            else:
                cleaned.append("-")
        slug = "".join(cleaned)
        while "--" in slug:
            slug = slug.replace("--", "-")
        return slug.strip("-") or "untitled"


def generate_tender_quote_pack(
    tender: NormalizedTender,
    *,
    base_output_dir: str | None = None,
) -> NormalizedTender:
    generator = TenderQuotePackGenerator(base_output_dir=base_output_dir)
    return generator.generate_for_tender(tender)
