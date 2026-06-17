from pathlib import Path

from app.services.tender_form_priority_engine import TenderFormPriorityEngine


def test_discover_documents_includes_txt_and_csv_source_bundle_files(tmp_path: Path) -> None:
    overview = tmp_path / "rfq_overview.txt"
    overview.write_text("RFQ overview", encoding="utf-8")

    pricing = tmp_path / "pricing_schedule.csv"
    pricing.write_text("pricing schedule,,,", encoding="utf-8")

    engine = TenderFormPriorityEngine()
    docs = engine.discover_documents(tmp_path, enable_archive_extract=False)

    paths = {Path(doc.path).name for doc in docs}
    assert "rfq_overview.txt" in paths
    assert "pricing_schedule.csv" in paths
