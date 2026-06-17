from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fixture_backed_fresh_intake_seeds_live_queue_and_artifacts(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_fixture_backed_fresh_intake.py"), "fixture_backed_fresh_intake")
    runtime_root = tmp_path / "runtime"
    manual_root = runtime_root / "manual_production"
    manual_root.mkdir(parents=True, exist_ok=True)

    runtime_paths = type("RuntimePaths", (), {"runtime_root": runtime_root, "manual_production_dir": manual_root})()

    monkeypatch.setattr(module, "get_runtime_paths", lambda: runtime_paths)

    captured_live_rfq = {}

    def _fake_upsert(item):
        captured_live_rfq.update(item)
        return {"status": "ok", "count": 1, "items": [item]}

    monkeypatch.setattr(module.LiveRFQStore, "upsert", staticmethod(_fake_upsert))

    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "tender_id": "ignored-by-harness",
                "title": "Fixture Backed Intake",
                "buyer_name": "Metro Procurement Unit",
                "province": "Gauteng",
                "category": "supply and delivery",
                "closing_date": "2026-11-30T12:00:00+00:00",
                "source_files": ["source_files/example.pdf"],
                "line_items": [
                    {"line_number": 1, "description": "A4 copy paper", "quantity": 10, "unit": "Box"},
                    {"line_number": 2, "description": "Ballpoint pens", "quantity": 5, "unit": "Pack"},
                ],
                "expected_exclusion_status": "eligible",
                "expected_minimum_profit_result": "above_margin",
                "expected_submission_ready": True,
                "pricing_file": "source_files/example_pricing.xlsx",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    class _FakeHarness:
        def run_fixture(self, fixture_path):
            copied = Path(fixture_path)
            tender_id = copied.stem.upper()
            tender_root = manual_root / "submission_packages" / tender_id
            review_root = manual_root / "review_ready_bundles" / tender_id
            governed_root = manual_root / "governed_submissions" / tender_id
            execution_root = manual_root / "submission_executions" / tender_id
            tender_root.mkdir(parents=True, exist_ok=True)
            review_root.mkdir(parents=True, exist_ok=True)
            governed_root.mkdir(parents=True, exist_ok=True)
            execution_root.mkdir(parents=True, exist_ok=True)

            csv_path = tender_root / f"{tender_id}__buyer_pricing_schedule.csv"
            csv_path.write_text(
                "line_no,description,quantity,unit_price,line_total\n"
                "1,A4 copy paper,10,0.00,0.00\n"
                "2,Ballpoint pens,5,0.00,0.00\n",
                encoding="utf-8",
            )
            (tender_root / f"{tender_id}__quote_pack.pdf").write_text("placeholder", encoding="utf-8")
            (tender_root / f"{tender_id}__quote_pack.json").write_text("{}", encoding="utf-8")
            (tender_root / f"{tender_id}__quote_pack_manifest.json").write_text(json.dumps({"package_status": "ready"}), encoding="utf-8")
            (tender_root / f"{tender_id}__submission_package_manifest.json").write_text(json.dumps({"package_status": "ready"}), encoding="utf-8")
            (tender_root / f"{tender_id}_submission_pack_manifest.txt").write_text("manifest", encoding="utf-8")
            (review_root / "review_ready_quote_pack.json").write_text(json.dumps({"review_ready": True, "submission_ready": True}), encoding="utf-8")
            (review_root / "review_ready_quote_pack_manifest.json").write_text(json.dumps({"bundle_status": "ready"}), encoding="utf-8")
            (review_root / "audit_export.json").write_text("[]", encoding="utf-8")
            (review_root / "operator_actions.json").write_text("[]", encoding="utf-8")
            return {
                "passed": True,
                "tender_id": tender_id,
                "quality_summary": {
                    "rfq_extraction": {
                        "title": "Fixture Backed Intake",
                        "buyer_name": "Metro Procurement Unit",
                        "province": "Gauteng",
                        "category": "supply and delivery",
                        "closing_date": "2026-11-30T12:00:00+00:00",
                    }
                },
                "artifacts_created": [str(csv_path)],
            }

    monkeypatch.setattr(module, "E2ERFQHarness", _FakeHarness)

    result = module.run_fixture_backed_fresh_intake(str(fixture), str(runtime_root / "live_rfqs.json"))

    assert result["status"] == "ok"
    tender_id = result["tender_id"]
    assert tender_id == captured_live_rfq["rfq_id"]
    assert captured_live_rfq["eligible"] is True
    assert captured_live_rfq["quote_ready"] is True

    pricing_file = manual_root / "submission_packages" / tender_id / f"{tender_id}__manual_pricing.json"
    assert pricing_file.exists()
    pricing_payload = json.loads(pricing_file.read_text(encoding="utf-8"))
    assert pricing_payload["items"]
    assert pricing_payload["items"][0]["recommended"] is True
    assert pricing_payload["items"][0]["unit_price"] > 0
    assert pricing_payload["items"][1]["unit_price"] > 0
    assert (manual_root / "review_ready_bundles" / tender_id).exists()


def test_harvest_backed_fresh_intake_prefers_live_harvest_candidate(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_fixture_backed_fresh_intake.py"), "harvest_backed_fresh_intake")
    runtime_root = tmp_path / "runtime"
    manual_root = runtime_root / "manual_production"
    manual_root.mkdir(parents=True, exist_ok=True)

    runtime_paths = type("RuntimePaths", (), {"runtime_root": runtime_root, "manual_production_dir": manual_root})()
    monkeypatch.setattr(module, "get_runtime_paths", lambda: runtime_paths)

    captured_live_rfq = {}

    def _fake_upsert(item):
        captured_live_rfq.update(item)
        return {"status": "ok", "count": 1, "items": [item]}

    monkeypatch.setattr(module.LiveRFQStore, "upsert", staticmethod(_fake_upsert))

    harvest_source_file = tmp_path / "harvest_sources.json"
    harvest_source_file.write_text(json.dumps({"sources": [{"name": "Live Portal", "type": "web", "url": "https://example.org"}]}), encoding="utf-8")

    def _fake_harvest(**kwargs):
        assert kwargs["source_file"] == str(harvest_source_file)
        return {
            "status": "ok",
            "items": [
                {
                    "rfq_id": "HARVESTED-001",
                    "title": "Harvested Office Supplies",
                    "description": "Harvested Office Supplies",
                    "buyer_name": "Metro Procurement Unit",
                    "buyer": "Metro Procurement Unit",
                    "province": "Gauteng",
                    "category": "Office Consumables",
                    "submission_type": "email",
                    "submission_method": "email",
                    "source_name": "Live Portal",
                    "source_url": "https://example.org/tenders/h1",
                    "document_urls": ["https://example.org/tenders/h1/rfq.pdf"],
                    "status": "Quote Ready",
                    "pipeline_status": "quote_ready_validated",
                    "eligible": True,
                    "quote_ready": True,
                    "estimated_profit": 45000.0,
                    "gross_margin_ratio": 0.30,
                    "estimated_contract_value": 150000.0,
                    "line_items": [
                        {"line_number": 1, "description": "A4 copy paper", "quantity": 12, "unit_price": 0.0, "line_total": 0.0},
                        {"line_number": 2, "description": "Ballpoint pens", "quantity": 6, "unit_price": 0.0, "line_total": 0.0},
                    ],
                }
            ],
        }

    monkeypatch.setattr(module, "run_national_tender_radar", _fake_harvest)

    result = module.run_fixture_backed_fresh_intake(
        str(tmp_path / "unused-fixture.json"),
        str(runtime_root / "live_rfqs.json"),
        harvest_source_file=str(harvest_source_file),
        harvest_max_sources=1,
        fallback_fixture="",
    )

    assert result["status"] == "ok"
    tender_id = result["tender_id"]
    assert tender_id == captured_live_rfq["rfq_id"]
    assert captured_live_rfq["eligible"] is True
    assert captured_live_rfq["quote_ready"] is True

    pricing_file = manual_root / "submission_packages" / tender_id / f"{tender_id}__manual_pricing.json"
    assert pricing_file.exists()
    pricing_payload = json.loads(pricing_file.read_text(encoding="utf-8"))
    assert pricing_payload["items"]
    assert pricing_payload["items"][0]["recommended"] is True
    assert pricing_payload["items"][0]["unit_price"] > 0
    assert pricing_payload["items"][1]["unit_price"] > 0
    assert (manual_root / "review_ready_bundles" / tender_id).exists()


def test_harvest_backed_fresh_intake_requires_live_harvest_when_requested(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_fixture_backed_fresh_intake.py"), "strict_harvest_backed_fresh_intake")
    runtime_root = tmp_path / "runtime"
    manual_root = runtime_root / "manual_production"
    manual_root.mkdir(parents=True, exist_ok=True)

    runtime_paths = type("RuntimePaths", (), {"runtime_root": runtime_root, "manual_production_dir": manual_root})()
    monkeypatch.setattr(module, "get_runtime_paths", lambda: runtime_paths)

    def _fake_harvest(**kwargs):
        assert kwargs["source_file"] == str(tmp_path / "harvest_sources.json")
        return {"status": "ok", "items": []}

    monkeypatch.setattr(module, "run_national_tender_radar", _fake_harvest)

    harvest_source_file = tmp_path / "harvest_sources.json"
    harvest_source_file.write_text(json.dumps({"sources": [{"name": "Live Portal", "type": "web", "url": "https://example.org"}]}), encoding="utf-8")

    try:
        module.run_fixture_backed_fresh_intake(
            str(tmp_path / "unused-fixture.json"),
            str(runtime_root / "live_rfqs.json"),
            harvest_source_file=str(harvest_source_file),
            harvest_max_sources=1,
            fallback_fixture=str(tmp_path / "fallback.json"),
            require_live_harvest=True,
        )
    except SystemExit as exc:
        assert "Live harvest did not produce a runnable RFQ candidate" in str(exc)
    else:
        raise AssertionError("expected strict live harvest mode to fail when no candidate is available")


def test_queue_refresh_source_file_generates_fresh_tender_id(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_fixture_backed_fresh_intake.py"), "queue_refresh_backed_fresh_intake")
    runtime_root = tmp_path / "runtime"
    manual_root = runtime_root / "manual_production"
    manual_root.mkdir(parents=True, exist_ok=True)

    runtime_paths = type("RuntimePaths", (), {"runtime_root": runtime_root, "manual_production_dir": manual_root})()
    monkeypatch.setattr(module, "get_runtime_paths", lambda: runtime_paths)

    captured_live_rfq = {}

    def _fake_upsert(item):
        captured_live_rfq.update(item)
        return {"status": "ok", "count": 1, "items": [item]}

    monkeypatch.setattr(module.LiveRFQStore, "upsert", staticmethod(_fake_upsert))

    def _fake_harvest(**kwargs):
        assert kwargs["source_file"].endswith("queue_refresh_sources.json")
        return {
            "status": "ok",
            "items": [
                {
                    "rfq_id": "RFQ 12345",
                    "title": "RFQ 12345 Supply and delivery of office supplies for 12 months",
                    "description": "RFQ 12345 Supply and delivery of office supplies for 12 months",
                    "buyer_name": "National Treasury eTenders",
                    "buyer": "National Treasury eTenders",
                    "province": "",
                    "category": "",
                    "submission_type": "portal",
                    "submission_method": "portal",
                    "source_name": "National Treasury eTenders",
                    "source_url": "https://www.etenders.gov.za/Home/opportunities",
                    "document_urls": ["https://www.etenders.gov.za/Home/opportunities"],
                    "status": "Quote Ready",
                    "pipeline_status": "quote_ready_validated",
                    "eligible": True,
                    "quote_ready": True,
                    "estimated_profit": 45000.0,
                    "gross_margin_ratio": 0.30,
                    "estimated_contract_value": 150000.0,
                    "line_items": [
                        {"line_number": 1, "description": "A4 copy paper", "quantity": 12, "unit_price": 0.0, "line_total": 0.0},
                    ],
                }
            ],
        }

    monkeypatch.setattr(module, "run_national_tender_radar", _fake_harvest)

    result = module.run_fixture_backed_fresh_intake(
        str(tmp_path / "unused-fixture.json"),
        str(runtime_root / "live_rfqs.json"),
        harvest_source_file=str(Path("/Users/cash/Documents/app/data/queue_refresh_sources.json")),
        harvest_max_sources=1,
        fallback_fixture="",
        require_live_harvest=True,
    )

    assert result["status"] == "ok"
    assert result["tender_id"].startswith("FRESH_REFRESH_")
    assert result["tender_id"] != "RFQ 12345"
    assert captured_live_rfq["rfq_id"] == result["tender_id"]
    assert Path(result["source_quote_boq"]).exists()
    assert Path(result["root_source_quote_boq"]).exists()
    assert Path(result["root_source_quote_pdf"]).exists()
