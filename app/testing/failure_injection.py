from __future__ import annotations


def simulate_db_write_unavailable(*args, **kwargs):
    return {"blockers": ["db write unavailable"]}


def simulate_interrupted_lifecycle(*args, **kwargs):
    return {"blockers": ["lifecycle interrupted"], "interrupted": True}


def simulate_invalid_transition(*args, **kwargs):
    return {"blockers": ["invalid workflow transition"]}


def simulate_malformed_json_fixture(*args, **kwargs):
    return {"blockers": ["malformed json fixture"]}


def simulate_missing_pricing_file(*args, **kwargs):
    return {"blockers": ["pricing file missing"]}


def simulate_missing_quote_pack(*args, **kwargs):
    return {"blockers": ["quote pack missing"]}


def simulate_missing_source_file(*args, **kwargs):
    return {"blockers": ["source file missing"]}
