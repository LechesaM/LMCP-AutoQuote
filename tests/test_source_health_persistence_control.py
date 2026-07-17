import json

from app.services import tender_harvester


def test_save_source_health_does_not_write_when_persistence_disabled(
    monkeypatch,
    tmp_path,
):
    health_path = tmp_path / "source_health.json"
    monkeypatch.setattr(tender_harvester, "SOURCE_HEALTH_FILE", health_path)

    tender_harvester._save_source_health(
        {"Source A": {"name": "Source A"}},
        persist=False,
    )

    assert not health_path.exists()


def test_save_source_health_writes_when_persistence_enabled(
    monkeypatch,
    tmp_path,
):
    health_path = tmp_path / "source_health.json"
    monkeypatch.setattr(tender_harvester, "SOURCE_HEALTH_FILE", health_path)

    tender_harvester._save_source_health(
        {"Source A": {"name": "Source A"}},
        persist=True,
    )

    assert json.loads(health_path.read_text(encoding="utf-8")) == {
        "Source A": {"name": "Source A"}
    }


def test_record_source_result_suppresses_file_mutation_when_disabled(
    monkeypatch,
    tmp_path,
):
    health_path = tmp_path / "source_health.json"
    health_path.write_text(
        json.dumps({"Existing": {"name": "Existing"}}),
        encoding="utf-8",
    )
    before = health_path.read_text(encoding="utf-8")
    monkeypatch.setattr(tender_harvester, "SOURCE_HEALTH_FILE", health_path)

    tender_harvester._record_source_result(
        {"name": "Source A"},
        ok=True,
        harvested=2,
        persist_source_health=False,
    )

    assert health_path.read_text(encoding="utf-8") == before


def test_record_source_result_writes_by_default_for_backward_compatibility(
    monkeypatch,
    tmp_path,
):
    health_path = tmp_path / "source_health.json"
    monkeypatch.setattr(tender_harvester, "SOURCE_HEALTH_FILE", health_path)

    tender_harvester._record_source_result(
        {"name": "Source A"},
        ok=True,
        harvested=2,
    )

    payload = json.loads(health_path.read_text(encoding="utf-8"))
    assert payload["Source A"]["last_harvested"] == 2
    assert payload["Source A"]["failure_count"] == 0


def test_v53_source_health_update_suppresses_file_mutation_when_disabled(
    monkeypatch,
    tmp_path,
):
    health_path = tmp_path / "source_health.json"
    health_path.write_text(
        json.dumps({"Existing": {"name": "Existing"}}),
        encoding="utf-8",
    )
    before = health_path.read_text(encoding="utf-8")
    monkeypatch.setattr(tender_harvester, "SOURCE_HEALTH_FILE", health_path)

    row = tender_harvester._v53_update_source_health_after_scan(
        {"name": "Source A", "type": "web"},
        harvested_count=1,
        candidate_count=1,
        response_time=0.25,
        persist_source_health=False,
    )

    assert row["source_name"] == "Source A"
    assert row["candidate_total"] == 1
    assert health_path.read_text(encoding="utf-8") == before


def test_v53_source_health_update_writes_when_enabled(
    monkeypatch,
    tmp_path,
):
    health_path = tmp_path / "source_health.json"
    monkeypatch.setattr(tender_harvester, "SOURCE_HEALTH_FILE", health_path)

    tender_harvester._v53_update_source_health_after_scan(
        {"name": "Source A", "type": "web"},
        harvested_count=1,
        candidate_count=1,
        response_time=0.25,
        persist_source_health=True,
    )

    payload = json.loads(health_path.read_text(encoding="utf-8"))
    assert payload["Source A"]["candidate_total"] == 1
    assert payload["Source A"]["scan_total"] == 1


def test_temporarily_bad_non_core_source_is_suppressed(
    monkeypatch,
    tmp_path,
):
    health_path = tmp_path / "source_health.json"
    health_path.write_text(
        json.dumps({"Bad Source": {"failure_count": 2}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(tender_harvester, "SOURCE_HEALTH_FILE", health_path)

    selected = tender_harvester.select_sources_for_cycle(
        [
            {"name": "Bad Source", "type": "web", "priority": 1},
            {"name": "Good Source", "type": "web", "priority": 2},
        ],
        max_sources_per_cycle=5,
        include_bad_sources=False,
    )

    assert [source["name"] for source in selected] == ["Good Source"]


def test_include_bad_sources_allows_explicit_operator_override(
    monkeypatch,
    tmp_path,
):
    health_path = tmp_path / "source_health.json"
    health_path.write_text(
        json.dumps({"Bad Source": {"failure_count": 2}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(tender_harvester, "SOURCE_HEALTH_FILE", health_path)

    selected = tender_harvester.select_sources_for_cycle(
        [
            {"name": "Bad Source", "type": "web", "priority": 1},
            {"name": "Good Source", "type": "web", "priority": 2},
        ],
        max_sources_per_cycle=5,
        include_bad_sources=True,
    )

    assert [source["name"] for source in selected] == [
        "Bad Source",
        "Good Source",
    ]


def test_corrupt_source_health_fails_safe_without_suppressing_all_sources(
    monkeypatch,
    tmp_path,
):
    health_path = tmp_path / "source_health.json"
    health_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(tender_harvester, "SOURCE_HEALTH_FILE", health_path)

    selected = tender_harvester.select_sources_for_cycle(
        [
            {"name": "Source A", "type": "web", "priority": 2},
            {"name": "Source B", "type": "web", "priority": 1},
        ],
        max_sources_per_cycle=5,
        include_bad_sources=False,
    )

    assert [source["name"] for source in selected] == [
        "Source B",
        "Source A",
    ]
