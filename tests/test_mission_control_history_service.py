from __future__ import annotations

from app.services.mission_control_history_service import (
    build_mission_control_trends,
    get_mission_control_history,
    record_mission_control_snapshot,
)


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


def test_mission_control_trends_compute_percent_change(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LMCP_MISSION_CONTROL_HISTORY_PATH", str(tmp_path / "mission_control_history.json"))

    for day in range(1, 15):
        record_mission_control_snapshot(
            {
                "generatedAt": f"2026-06-{day:02d}T08:00:00Z",
                "harvestedCount": day,
                "submittedCount": day * 2,
                "estimatedProfit": day * 1000,
                "provinceDistribution": {"GP": 1, "FS": 0, "KZN": 1},
            }
        )

    trends = build_mission_control_trends()

    assert trends["status"] == "configured"
    assert trends["windows"]["7d"]["rfqsHarvested"]["current"] == 77
    assert trends["windows"]["7d"]["rfqsHarvested"]["previous"] == 28
    assert trends["windows"]["7d"]["rfqsHarvested"]["change"] == 175.0
    assert trends["windows"]["7d"]["rfqsHarvested"]["direction"] == "up"
    assert trends["windows"]["7d"]["provinceActivity"]["current"] == 14
    assert trends["windows"]["7d"]["provinceActivity"]["previous"] == 14
    assert trends["windows"]["7d"]["provinceActivity"]["change"] == 0.0
    assert trends["windows"]["7d"]["provinceActivity"]["direction"] == "flat"
    assert trends["windows"]["30d"]["status"] == "insufficient_history"


def test_mission_control_trends_include_current_snapshot(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LMCP_MISSION_CONTROL_HISTORY_PATH", str(tmp_path / "mission_control_history.json"))

    for day in range(1, 14):
        record_mission_control_snapshot(
            {
                "generatedAt": f"2026-06-{day:02d}T08:00:00Z",
                "harvestedCount": day,
                "submittedCount": day,
                "estimatedProfit": day * 1000,
                "provinceDistribution": {"GP": 1},
            }
        )

    trends = build_mission_control_trends(
        current_snapshot={
            "generatedAt": "2026-06-14T12:00:00Z",
            "harvestedCount": 14,
            "submittedCount": 14,
            "estimatedProfit": 14000,
            "provinceDistribution": {"GP": 1},
        }
    )

    assert trends["windows"]["7d"]["status"] == "configured"
    assert trends["windows"]["7d"]["rfqsHarvested"]["current"] == 77
