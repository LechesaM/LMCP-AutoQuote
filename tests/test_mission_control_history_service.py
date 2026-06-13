from __future__ import annotations

from app.services.mission_control_history_service import get_mission_control_history, record_mission_control_snapshot


def test_mission_control_history_upserts_one_snapshot_per_day(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LMCP_MISSION_CONTROL_HISTORY_PATH", str(tmp_path / "mission_control_history.json"))

    record_mission_control_snapshot({"generatedAt": "2026-06-12T08:00:00Z", "harvestedCount": 3})
    record_mission_control_snapshot({"generatedAt": "2026-06-12T16:30:00Z", "harvestedCount": 7})

    history = get_mission_control_history(days=30)

    assert history["status"] == "configured"
    assert len(history["items"]) == 1
    assert history["items"][0]["date"] == "2026-06-12"
    assert history["items"][0]["snapshot"]["harvestedCount"] == 7


def test_mission_control_history_filters_by_window(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LMCP_MISSION_CONTROL_HISTORY_PATH", str(tmp_path / "mission_control_history.json"))

    record_mission_control_snapshot({"generatedAt": "2026-06-01T08:00:00Z", "harvestedCount": 2})
    record_mission_control_snapshot({"generatedAt": "2026-06-12T08:00:00Z", "harvestedCount": 9})

    history = get_mission_control_history(days=7)

    assert history["status"] == "configured"
    assert len(history["items"]) == 1
    assert history["items"][0]["date"] == "2026-06-12"
