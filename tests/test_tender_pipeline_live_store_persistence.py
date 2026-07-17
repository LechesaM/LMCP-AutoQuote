from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from app.api import tender_pipeline_api
from app.services import live_rfq_store


def _rfq(reference: str, buyer: str = "Metro Buyer") -> Dict[str, Any]:
    return {
        "title": f"Supply of goods {reference}",
        "description": f"Supply and delivery for {reference}",
        "buyer_name": buyer,
        "buyer_rfq_number": reference,
        "rfq_number": reference,
        "submission_method": "email",
        "eligible": True,
    }


def test_live_store_persistence_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[Dict[str, Any]] = []
    monkeypatch.setattr(tender_pipeline_api.LiveRFQStore, "upsert_rfq", lambda item: calls.append(item))

    result = tender_pipeline_api._persist_result_to_live_store_if_requested(
        result_dict={"results": [_rfq("RFQ-DISABLED-1")]},
        persist_to_live_store=False,
    )

    assert calls == []
    assert result["live_store_persisted"] is False
    assert result["live_store_persisted_count"] == 0


def test_single_rfq_result_persists_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[Dict[str, Any]] = []
    monkeypatch.setattr(tender_pipeline_api.LiveRFQStore, "upsert_rfq", lambda item: calls.append(dict(item)))

    result = tender_pipeline_api._persist_result_to_live_store_if_requested(
        result_dict=_rfq("RFQ-SINGLE-1", buyer="Single Buyer"),
        persist_to_live_store=True,
    )

    assert result["live_store_persisted"] is True
    assert result["live_store_persisted_count"] == 1
    assert len(calls) == 1
    assert calls[0]["buyer_rfq_number"] == "RFQ-SINGLE-1"
    assert calls[0]["buyer_name"] == "Single Buyer"


def test_multi_rfq_result_persists_each_distinct_row(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[Dict[str, Any]] = []
    monkeypatch.setattr(tender_pipeline_api.LiveRFQStore, "upsert_rfq", lambda item: calls.append(dict(item)))

    result = tender_pipeline_api._persist_result_to_live_store_if_requested(
        result_dict={"results": [_rfq("RFQ-MULTI-1"), _rfq("RFQ-MULTI-2"), _rfq("RFQ-MULTI-3")]},
        persist_to_live_store=True,
    )

    assert result["live_store_persisted"] is True
    assert result["live_store_persisted_count"] == 3
    assert [call["buyer_rfq_number"] for call in calls] == [
        "RFQ-MULTI-1",
        "RFQ-MULTI-2",
        "RFQ-MULTI-3",
    ]


def test_invalid_rows_are_skipped_and_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[Dict[str, Any]] = []
    monkeypatch.setattr(tender_pipeline_api.LiveRFQStore, "upsert_rfq", lambda item: calls.append(dict(item)))

    result = tender_pipeline_api._persist_result_to_live_store_if_requested(
        result_dict={"results": [_rfq("RFQ-VALID-1"), {}, "bad-row", _rfq("RFQ-VALID-2")]},
        persist_to_live_store=True,
    )

    assert result["live_store_persisted"] is True
    assert result["live_store_persisted_count"] == 2
    assert result["live_store_skipped_count"] == 2
    assert [row["index"] for row in result["live_store_skipped_rows"]] == [1, 2]
    assert [call["buyer_rfq_number"] for call in calls] == ["RFQ-VALID-1", "RFQ-VALID-2"]


def test_partial_persistence_failure_reports_affected_rfq(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[str] = []

    def fake_upsert(item: Dict[str, Any]) -> None:
        calls.append(str(item.get("buyer_rfq_number")))
        if item.get("buyer_rfq_number") == "RFQ-FAIL-2":
            raise RuntimeError("simulated write failure")

    monkeypatch.setattr(tender_pipeline_api.LiveRFQStore, "upsert_rfq", fake_upsert)

    result = tender_pipeline_api._persist_result_to_live_store_if_requested(
        result_dict={"results": [_rfq("RFQ-FAIL-1"), _rfq("RFQ-FAIL-2"), _rfq("RFQ-FAIL-3")]},
        persist_to_live_store=True,
    )

    assert calls == ["RFQ-FAIL-1", "RFQ-FAIL-2", "RFQ-FAIL-3"]
    assert result["live_store_persisted"] is False
    assert result["live_store_persisted_count"] == 2
    assert result["live_store_persist_errors"] == [
        {"index": 1, "rfq_key": "RFQ-FAIL-2", "error": "simulated write failure"}
    ]
    assert [row["rfq_key"] for row in result["live_store_persisted_rows"]] == ["RFQ-FAIL-1", "RFQ-FAIL-3"]


def test_no_production_runtime_writes_when_upsert_is_monkeypatched(monkeypatch: pytest.MonkeyPatch) -> None:
    protected = {
        Path("runtime/live_rfqs.json").resolve(),
        Path("runtime/rfq_lifecycle/rfqs.json").resolve(),
    }
    write_attempts: List[Path] = []
    original_write_text = Path.write_text

    def guard_write_text(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self.resolve() in protected:
            write_attempts.append(self.resolve())
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", guard_write_text)
    monkeypatch.setattr(tender_pipeline_api.LiveRFQStore, "upsert_rfq", lambda item: {"status": "ok"})

    result = tender_pipeline_api._persist_result_to_live_store_if_requested(
        result_dict={"results": [_rfq("RFQ-NO-PROD-WRITE-1")]},
        persist_to_live_store=True,
    )

    assert result["live_store_persisted"] is True
    assert write_attempts == []


def test_persistence_bridge_reads_back_from_temporary_live_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    temp_store = tmp_path / "live_rfqs.json"
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", temp_store)

    result = tender_pipeline_api._persist_result_to_live_store_if_requested(
        result_dict={"results": [_rfq("RFQ-BRIDGE-1"), _rfq("RFQ-BRIDGE-2"), {}, _rfq("RFQ-BRIDGE-3")]},
        persist_to_live_store=True,
    )

    assert result["live_store_persisted"] is True
    assert result["live_store_persisted_count"] == 3
    payload = json.loads(temp_store.read_text(encoding="utf-8"))
    assert payload["count"] == 3
    assert [item["buyer_rfq_number"] for item in payload["items"]] == [
        "RFQ-BRIDGE-1",
        "RFQ-BRIDGE-2",
        "RFQ-BRIDGE-3",
    ]
    read_back = live_rfq_store.LiveRFQStore.get_all()
    assert read_back["count"] == 3
    assert [item["buyer_rfq_number"] for item in read_back["items"]] == [
        "RFQ-BRIDGE-1",
        "RFQ-BRIDGE-2",
        "RFQ-BRIDGE-3",
    ]
