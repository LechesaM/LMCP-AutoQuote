from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.core import workflow_state_engine
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.domain.pricing import PricingDecision
from app.domain.quote import QuotePack, QuotePackArtifact
from app.domain.rfq import RFQRecord
from app.domain.workflow import WorkflowStage
from app.qualification.qualification_engine import qualify_rfq
from app.persistence import jsonl_compat
from app.quality.context import build_quality_context
from app.quality.extraction_quality import build_rfq_extraction_quality_report
from app.quality.pricing_schedule_quality import build_pricing_schedule_quality_report
from app.quality.quote_pack_quality import build_quote_pack_quality_report
from app.quality.supplier_pricing_quality import build_supplier_comparison_summary
from app.services import manual_approval_service, submission_proof_service, submission_review_service
from app.testing.rfq_fixture_loader import load_fixture
from app.testing.workflow_replay import replay_workflow_history

from app.domain.base import StrictBaseModel, utc_now


class ProductionValidationResult(StrictBaseModel):
    tender_id: str = ""
    passed: bool = False
    final_stage: str = ""
    blockers: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    artifacts_created: List[str] = Field(default_factory=list)
    workflow_history: List[Dict[str, Any]] = Field(default_factory=list)
    persistence_verified: bool = False
    audit_verified: bool = False
    manual_submission_preserved: bool = True
    source_fixture: str = ""
    quality_summary: Dict[str, Any] = Field(default_factory=dict)
    qualification_summary: Dict[str, Any] = Field(default_factory=dict)
    qualification_result: Dict[str, Any] = Field(default_factory=dict)
    updated_at: Any = None

def _ensure_text_file(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _ensure_json_file(path: Path, payload: Dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(path)


def _append_workflow_state(tender_id: str, stage: WorkflowStage, details: Dict[str, Any]) -> None:
    current = workflow_state_engine.get_current_state(tender_id).stage
    if current == stage:
        return
    workflow_state_engine.record_transition(
        tender_id=tender_id,
        from_stage=current,
        to_stage=stage,
        actor="e2e-harness",
        reason=f"e2e harness transition to {stage.value}",
        details=details,
    )


class E2ERFQHarness:
    def __init__(self) -> None:
        self.paths = get_runtime_paths()
        self.runtime_config = get_runtime_config()

    def run_fixture(self, fixture_path: Path | str) -> Dict[str, Any]:
        fixture = load_fixture(Path(fixture_path))
        return self.run_lifecycle(fixture)

    def run_folder(self, folder_path: Path | str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for path in sorted(Path(folder_path).glob("*.json")):
            results.append(self.run_fixture(path))
        return results

    def _create_rfq_record(self, rfq_payload: Dict[str, Any]) -> Dict[str, Any]:
        closing_date = rfq_payload.get("closing_date")
        rfq = RFQRecord.validate_payload(
            {
                "tender_id": rfq_payload.get("tender_id", ""),
                "title": rfq_payload.get("title", ""),
                "buyer_name": rfq_payload.get("buyer_name", ""),
                "province": rfq_payload.get("province", ""),
                "category": rfq_payload.get("category", ""),
                "closing_date": closing_date or None,
                "source_path": rfq_payload.get("source_files", [""])[0] if rfq_payload.get("source_files") else "",
                "documents": rfq_payload.get("rfq_record", {}).get("documents", []),
                "line_items": rfq_payload.get("rfq_record", {}).get("line_items", []),
            }
        ).to_jsonable_dict()
        return rfq

    def _evaluate_exclusions(self, rfq_record: Dict[str, Any]) -> List[str]:
        category = str(rfq_record.get("category") or "").lower()
        title = str(rfq_record.get("title") or "").lower()
        blockers: List[str] = []
        excluded_tokens = {"catering", "petrol", "diesel", "medical consumables", "it equipment"}
        if any(token in category or token in title for token in excluded_tokens):
            blockers.append("excluded category")
        if not rfq_record.get("source_path"):
            blockers.append("missing source document")
        return blockers

    def _simulate_pricing(self, rfq_record: Dict[str, Any], fixture: Dict[str, Any]) -> PricingDecision:
        expected = str(fixture.get("expected_minimum_profit_result") or "").lower()
        if expected == "below_margin":
            profit = 1000.0
            margin = 0.1
        else:
            profit = 45000.0
            margin = 0.3
        return PricingDecision.validate_payload(
            {
                "tender_id": rfq_record.get("tender_id", ""),
                "quantity": 1,
                "unit_cost": 100.0,
                "markup_ratio": 0.25,
                "vat_rate": 0.15,
                "delivery_cost": 0.0,
                "gross_margin_ratio": margin,
                "profit_amount": profit,
                "minimum_profit_required": 30000.0,
                "minimum_supply_margin_ratio": 0.25,
            }
        )

    def _create_quote_pack(self, rfq_record: Dict[str, Any], pricing: PricingDecision) -> Dict[str, Any]:
        runtime_root = self.paths.manual_production_dir / "e2e_rfqs" / rfq_record["tender_id"]
        schedule_path = _ensure_text_file(
            runtime_root / f"{rfq_record['tender_id']}__buyer_pricing_schedule.csv",
            "\n".join(
                [
                    "line_number,description,quantity,unit,unit_price,total",
                    *[
                        ",".join(
                            [
                                str(line.get("line_number", "")),
                                str(line.get("description", "")).replace(",", " "),
                                str(line.get("quantity", "")),
                                str(line.get("unit", "")).replace(",", " "),
                                str(line.get("unit_price", 0.0)),
                                str(round(float(line.get("quantity", 0) or 0) * float(line.get("unit_price", 0) or 0), 2)),
                            ]
                        )
                        for line in (rfq_record.get("line_items") or [])
                        if isinstance(line, dict)
                    ],
                ]
            ),
        )
        pdf_path = _ensure_text_file(runtime_root / f"{rfq_record['tender_id']}__quote_pack.pdf", "quote pack")
        manifest_path = _ensure_json_file(
            runtime_root / f"{rfq_record['tender_id']}__quote_pack_manifest.json",
            {
                "tender_id": rfq_record["tender_id"],
                "company_name": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
                "buyer_name": rfq_record.get("buyer_name", ""),
                "quote_number": rfq_record["tender_id"],
                "generated_pdf_path": str(runtime_root / f"{rfq_record['tender_id']}__quote_pack.pdf"),
                "generated_json_path": str(runtime_root / f"{rfq_record['tender_id']}__quote_pack.json"),
                "completed_buyer_schedule_path": schedule_path,
                "pricing_schedule_path": schedule_path,
                "manifest_path": str(runtime_root / f"{rfq_record['tender_id']}__quote_pack_manifest.json"),
                "validity_days": 30,
                "delivery_terms": "Standard delivery terms apply.",
                "vat_treatment": "VAT included at 15%",
                "signature_placeholder": "Operator approval required before submission.",
            },
        )
        json_path = _ensure_json_file(
            runtime_root / f"{rfq_record['tender_id']}__quote_pack.json",
            {
                **rfq_record,
                "company_name": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
                "company_contact_person": "E2E Operator",
                "company_email": "operations@example.com",
                "company_phone": "+27-000-000-000",
                "buyer_name": rfq_record.get("buyer_name", ""),
                "tender_reference": rfq_record["tender_id"],
                "pricing_schedule_path": schedule_path,
                "generated_pdf_path": pdf_path,
                "generated_json_path": str(runtime_root / f"{rfq_record['tender_id']}__quote_pack.json"),
                "completed_buyer_schedule_path": schedule_path,
                "manifest_path": manifest_path,
                "validity_days": 30,
                "delivery_terms": "Standard delivery terms apply.",
                "vat_treatment": "VAT included at 15%",
                "quote_pack_ready": True,
                "company_details_present": True,
                "buyer_details_present": True,
                "tender_reference_present": True,
                "pricing_schedule_present": True,
                "vat_treatment_shown": True,
                "validity_period_present": True,
                "delivery_terms_present": True,
                "signature_placeholder_present": True,
            },
        )
        quote_pack = QuotePack.validate_payload(
            {
                "tender_id": rfq_record["tender_id"],
                "company_name": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
                "company_contact_person": "E2E Operator",
                "company_email": "operations@example.com",
                "company_phone": "+27-000-000-000",
                "buyer_name": rfq_record.get("buyer_name", ""),
                "tender_reference": rfq_record["tender_id"],
                "pricing_schedule_path": schedule_path,
                "generated_pdf_path": pdf_path,
                "generated_json_path": json_path,
                "completed_buyer_schedule_path": schedule_path,
                "manifest_path": manifest_path,
                "validity_days": 30,
                "delivery_terms": "Standard delivery terms apply.",
                "vat_treatment": "VAT included at 15%",
                "quote_pack_ready": True,
                "company_details_present": True,
                "buyer_details_present": True,
                "tender_reference_present": True,
                "pricing_schedule_present": True,
                "vat_treatment_shown": True,
                "validity_period_present": True,
                "delivery_terms_present": True,
                "signature_placeholder_present": True,
                "artifacts": [
                    QuotePackArtifact.validate_payload({"artifact_type": "pdf", "path": pdf_path, "present": True}).to_jsonable_dict(),
                    QuotePackArtifact.validate_payload({"artifact_type": "json", "path": json_path, "present": True}).to_jsonable_dict(),
                    QuotePackArtifact.validate_payload({"artifact_type": "manifest", "path": manifest_path, "present": True}).to_jsonable_dict(),
                ],
            }
        ).to_jsonable_dict()
        jsonl_compat.persist_quote_pack(quote_pack)
        return quote_pack

    def _create_submission_pack(self, rfq_record: Dict[str, Any], quote_pack: Dict[str, Any]) -> Dict[str, Any]:
        runtime_root = self.paths.manual_production_dir / "e2e_rfqs" / rfq_record["tender_id"]
        path = _ensure_text_file(runtime_root / f"{rfq_record['tender_id']}_submission_pack_manifest.txt", "submission pack")
        return {"submission_pack_path": path, "submission_pack_present": True, "submission_ready": True}

    def _build_quality_summary(self, rfq: Dict[str, Any], quote_pack: Dict[str, Any]) -> Dict[str, Any]:
        rfq_report = build_rfq_extraction_quality_report(rfq)
        schedule_report = build_pricing_schedule_quality_report(
            {
                "completed_buyer_schedule_path": quote_pack.get("completed_buyer_schedule_path", ""),
                "pricing_schedule_path": quote_pack.get("pricing_schedule_path", ""),
                "rows": rfq.get("line_items") or [],
            }
        )
        quote_pack_report = build_quote_pack_quality_report(quote_pack)
        quality_context = build_quality_context(limit=50)
        supplier_report = build_supplier_comparison_summary(quality_context.get("supplier_quotes") or [])
        return {
            "rfq_extraction": rfq_report,
            "pricing_schedule": schedule_report,
            "quote_pack": quote_pack_report,
            "supplier_pricing": supplier_report,
        }

    def _build_qualification_summary(self, rfq: Dict[str, Any]) -> Dict[str, Any]:
        return qualify_rfq(rfq)

    def run_lifecycle(self, rfq_record: Dict[str, Any]) -> Dict[str, Any]:
        rfq = self._create_rfq_record(rfq_record)
        tender_id = rfq["tender_id"]
        blockers = self._evaluate_exclusions(rfq)
        artifacts: List[str] = []
        warnings: List[str] = []
        if blockers:
            workflow_state_engine.refuse_workflow(tender_id, actor="e2e-harness", reason="blocked rfq", details={"blockers": blockers})
            replay = replay_workflow_history(tender_id)
            current_state = workflow_state_engine.get_current_state(tender_id)
            qualification_result = self._build_qualification_summary(rfq)
            result = ProductionValidationResult(
                tender_id=tender_id,
                passed=False,
                final_stage=current_state.stage.value,
                blockers=blockers,
                warnings=warnings,
                artifacts_created=artifacts,
                workflow_history=replay.get("history", []),
                persistence_verified=not bool(replay.get("persistence_mismatch")),
                audit_verified=not bool(replay.get("missing_audit_events")),
                manual_submission_preserved=True,
                source_fixture=str(rfq_record.get("fixture_path") or ""),
                quality_summary=self._build_quality_summary(rfq, {"artifacts": []}),
                qualification_result=qualification_result,
                qualification_summary=qualification_result,
                updated_at=utc_now(),
            )
            return result.to_jsonable_dict()

        if not rfq.get("source_path") or not Path(str(rfq.get("source_path"))).exists():
            blockers.append("missing source document")
            workflow_state_engine.refuse_workflow(tender_id, actor="e2e-harness", reason="missing source document", details={"source_path": rfq.get("source_path", "")})
        else:
            _append_workflow_state(tender_id, WorkflowStage.EXTRACTED, {"source_path": rfq.get("source_path", "")})
            _append_workflow_state(tender_id, WorkflowStage.EVALUATED, {"evaluation": "complete"})
            pricing = self._simulate_pricing(rfq, rfq_record)
            if not pricing.approved:
                blockers.extend(pricing.refusal_blocker_reasons)
                workflow_state_engine.refuse_workflow(tender_id, actor="e2e-harness", reason="pricing below threshold", details={"blockers": pricing.refusal_blocker_reasons})
            else:
                _append_workflow_state(tender_id, WorkflowStage.PRICED, pricing.to_jsonable_dict())
                quote_pack = self._create_quote_pack(rfq, pricing)
                artifacts.extend([
                    quote_pack.get("generated_pdf_path", ""),
                    quote_pack.get("generated_json_path", ""),
                    quote_pack.get("manifest_path", ""),
                ])
                _append_workflow_state(tender_id, WorkflowStage.QUOTE_GENERATED, quote_pack)
                submission_pack = self._create_submission_pack(rfq, quote_pack)
                artifacts.append(submission_pack["submission_pack_path"])
                _append_workflow_state(tender_id, WorkflowStage.APPROVAL_REQUIRED, quote_pack)
                approval_record = manual_approval_service.build_manual_approval_record(
                    {
                        "tender_id": tender_id,
                        "quote_pack_quality_status": "approval_ready",
                        "warnings": [],
                    },
                    tender_id=tender_id,
                    tender_root=str(self.paths.manual_production_dir / "e2e_rfqs" / tender_id),
                    pricing_file=quote_pack.get("generated_json_path", ""),
                    operator_name="E2E Operator",
                    confirm_approval=True,
                )
                manual_approval_service.append_manual_approval(approval_record)
                submission_review = submission_review_service.build_submission_review_record(
                    tender_id=tender_id,
                    tender_root=str(self.paths.manual_production_dir / "e2e_rfqs" / tender_id),
                    pricing_file=quote_pack.get("generated_json_path", ""),
                    operator_name="E2E Reviewer",
                )
                submission_review_service.append_submission_review(submission_review)
                proof_record = submission_proof_service.build_submission_proof_record(
                    tender_id=tender_id,
                    tender_root=str(self.paths.manual_production_dir / "e2e_rfqs" / tender_id),
                    portal_name="eTenders",
                    submission_reference=f"SUB-{tender_id}",
                    submitted_by="E2E Submitter",
                    proof_file=quote_pack.get("generated_pdf_path", ""),
                )
                submission_proof_service.append_submission_proof(proof_record)

        replay = replay_workflow_history(tender_id)
        current_state = workflow_state_engine.get_current_state(tender_id)
        persistence_verified = not bool(replay.get("persistence_mismatch"))
        audit_verified = not bool(replay.get("missing_audit_events"))
        qualification_result = self._build_qualification_summary(rfq)
        result = ProductionValidationResult(
            tender_id=tender_id,
            passed=not blockers and current_state.stage is WorkflowStage.PROOF_RECORDED and replay.get("passed", False),
            final_stage=current_state.stage.value,
            blockers=blockers,
            warnings=warnings,
            artifacts_created=artifacts,
            workflow_history=replay.get("history", []),
            persistence_verified=persistence_verified,
            audit_verified=audit_verified,
            manual_submission_preserved=not bool(proof_record.get("final_submission_attempted", False)) if "proof_record" in locals() else True,
            source_fixture=str(rfq_record.get("fixture_path") or ""),
            quality_summary=self._build_quality_summary(rfq, quote_pack if "quote_pack" in locals() else {}),
            qualification_result=qualification_result,
            qualification_summary=qualification_result,
            updated_at=utc_now(),
        )
        return result.to_jsonable_dict()

    def produce_validation_result(self, fixture_path: Optional[Path | str] = None, folder_path: Optional[Path | str] = None) -> Dict[str, Any]:
        if fixture_path is not None:
            return self.run_fixture(fixture_path)
        if folder_path is not None:
            return {"results": self.run_folder(folder_path)}
        raise ValueError("fixture_path or folder_path is required")
