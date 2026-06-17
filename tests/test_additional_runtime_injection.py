from __future__ import annotations

import asyncio
import os
from pathlib import Path

os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")

from app.services import csd_monthly_refresh_service as csd_service
from app.services import sbd_completion_engine as sbd_service
from app.services import smart_upload_v47_4_service as smart_upload_service


def test_smart_upload_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    result = asyncio.run(smart_upload_service.run_smart_upload({"runtime_dir": str(runtime_dir)}))
    status = smart_upload_service.get_smart_upload_status(runtime_dir=str(runtime_dir))

    assert result["status"] == "assisted_required"
    assert status["files"]["runtime_dir"] == str(runtime_dir / "smart_upload_v47_4")
    assert (runtime_dir / "smart_upload_v47_4" / "last_upload.json").exists()


def test_sbd_completion_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    payload = {
        "buyer_rfq_number": "RFQ-9",
        "company_name": "Test Co",
        "registration_number": "REG-1",
        "tax_number": "TAX-1",
        "csd_number": "CSD-1",
        "director_name": "Director",
        "director_capacity": "Director",
        "signature_present": True,
        "date_signed": "2026-06-03",
        "bid_price": 1000,
        "vat_included": True,
        "pricing_schedule_completed": True,
        "validity_days": 30,
        "sbd_1_completed": True,
        "sbd_4_completed": True,
        "sbd_6_1_completed": True,
        "sbd_8_completed": True,
        "sbd_9_completed": True,
        "runtime_dir": str(runtime_dir),
    }

    result = asyncio.run(sbd_service.record_sbd_completion(payload))
    summary = sbd_service.get_sbd_completion_summary(runtime_dir=str(runtime_dir))

    assert result["sbd_ready"] is True
    assert summary["files"]["runtime_dir"] == str(runtime_dir / "sbd_completion")
    assert (runtime_dir / "sbd_completion" / "sbd_completion_status.json").exists()
    assert (runtime_dir / "sbd_completion" / "sbd_completion_history.json").exists()


def test_csd_refresh_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    result = csd_service.refresh_csd_report(force=False, runtime_dir=str(runtime_dir))
    status = csd_service.get_csd_refresh_status(runtime_dir=str(runtime_dir))

    assert result["status"] == "skipped"
    assert status["compliance_dir"] == str(runtime_dir / "compliance")
    assert (runtime_dir / "compliance" / "csd_refresh_status.json").exists()
