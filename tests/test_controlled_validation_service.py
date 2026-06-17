from __future__ import annotations

import json
from pathlib import Path

from app.services import controlled_validation_service as validation_service


def _write_pack(pack_dir: Path, *, pack_id: str, rfq_reference: str, title: str, readiness_score: int, boq_style: str, forms: list[str], missing_items: list[str] = None) -> None:
    pack_dir.mkdir(parents=True, exist_ok=True)
    missing_items = missing_items or []
    pack_dir.joinpath("submission_binder_readiness.json").write_text(
        json.dumps(
            {
                "created_at": "2026-05-27T00:00:00+00:00",
                "pack_id": pack_id,
                "rfq_reference": rfq_reference,
                "readiness": {
                    "submission_binder_score": readiness_score,
                    "missing_items": missing_items,
                    "blockers": [],
                    "pricing_completed": True,
                    "formal_quote_generated": True,
                    "returnables_review_completed": True,
                },
                "safety": {"local_only": True},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    pack_dir.joinpath("quote_pack_manifest.json").write_text(
        json.dumps(
            {
                "buyer": "LMCP",
                "created_at": "2026-05-27T00:00:00+00:00",
                "pack_id": pack_id,
                "rfq_reference": rfq_reference,
                "title": title,
                "readiness": {
                    "boq_found": boq_style != "missing",
                    "buyer_forms_found": True,
                    "quote_readiness_score": readiness_score,
                    "sbd_forms_found": bool(forms),
                },
                "files": [{"name": f"{pack_id}.json", "path": f"runtime/quote_compilation/{pack_id}/{pack_id}.json", "type": boq_style}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    pack_dir.joinpath("returnables_checklist.json").write_text(
        json.dumps(
            {
                "rfq_reference": rfq_reference,
                "boq_found": boq_style != "missing",
                "buyer_forms_found": True,
                "sbd_forms_found": bool(forms),
                "missing_items": missing_items,
                "sbd_forms": [{"name": name, "path": f"/tmp/{name}", "extension": ".doc"} for name in forms],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_controlled_validation_set_and_confidence_matrix(tmp_path, monkeypatch) -> None:
    runtime_dir = tmp_path / "runtime"
    output_root = runtime_dir / "quote_compilation"
    controlled_dir = runtime_dir / "controlled_validation"
    output_root.mkdir(parents=True, exist_ok=True)
    controlled_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(validation_service, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(validation_service, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(validation_service, "CONTROLLED_VALIDATION_DIR", controlled_dir)
    monkeypatch.setattr(validation_service, "CONTROLLED_VALIDATION_SET_FILE", controlled_dir / "controlled_validation_set.json")
    monkeypatch.setattr(validation_service, "CONTROLLED_VALIDATION_REPORT_FILE", controlled_dir / "controlled_validation_report.json")

    for index, (boq_style, forms) in enumerate(
        [
            ("json", ["SBD_1"]),
            ("csv", ["SBD_1", "SBD_4"]),
            ("spreadsheet", ["SBD_1", "SBD_4", "SBD_8"]),
            ("document-based", ["SBD_4", "SBD_6_1"]),
            ("json", ["SBD_1", "SBD_4", "SBD_6_1", "SBD_8", "SBD_9"]),
        ],
        start=1,
    ):
        pack_id = f"PACK-{index}"
        rfq_reference = f"RFQ-{index}"
        _write_pack(
            output_root / f"QCP-{index}-{pack_id}",
            pack_id=f"QCP-{index}-{pack_id}",
            rfq_reference=rfq_reference,
            title=f"Pack {index} {boq_style}",
            readiness_score=100,
            boq_style=boq_style,
            forms=forms,
        )

    monkeypatch.setattr(validation_service.quote_compilation_service, "get_submission_binder_gate", lambda pack_id, rfq_reference=None: {
        "status": "ok",
        "pack_id": pack_id,
        "rfq_reference": rfq_reference or pack_id,
        "can_prepare_submission": True,
        "can_submit_final": False,
        "manual_completion_allowed": True,
        "manual_completion_blocked_reason": "",
        "binder_score": 100,
        "blockers": [],
        "missing_returnables": [],
    })
    monkeypatch.setattr(validation_service.quote_compilation_service, "get_submission_binder_gate_checklist", lambda pack_id, rfq_reference=None, include_text=False: {
        "manual_completion_allowed": True,
        "manual_completion_blocked_reason": "",
    })
    monkeypatch.setattr(validation_service.quote_compilation_service, "get_submission_binder_gate_audit_log", lambda pack_id, rfq_reference=None: {
        "readiness_status": "manual_completion_recorded",
    })
    monkeypatch.setattr(validation_service, "get_submission_lock_status", lambda limit=50: {"verification": {"valid": True}, "summary": {"valid": True}})

    selected = validation_service.select_controlled_validation_set(limit=10, minimum=5)
    assert selected["selected_count"] == 5
    assert len({item["rfq_reference"] for item in selected["selected"]}) == 5

    report = validation_service.build_controlled_validation_report(limit=10, minimum=5)
    assert report["summary"]["selected_packs"] == 5
    assert report["summary"]["fully_clean_packs"] == 5
    assert report["confidence_score"] == 100
    assert report["status"] == "ready_for_v49"
    assert report["production_confidence_matrix"][0]["metric"] == "fully_clean_packs"

