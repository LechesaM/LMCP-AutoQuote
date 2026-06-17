from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from .e2e_rfq_harness import E2ERFQHarness


RUNTIME_DIR = Path("runtime")
EVIDENCE_DIR = RUNTIME_DIR / "execution_evidence"
DRY_DISPATCH_REGISTRY_FILE = EVIDENCE_DIR / "weekly_dry_dispatch_registry.jsonl"
LATEST_DRY_DISPATCH_REPORT_FILE = EVIDENCE_DIR / "latest_dry_dispatch_report.json"
DEFAULT_TIER_MANIFESTS_DIR = Path("tests/fixtures/manifests")


FAILURE_CATEGORY_RULES = (
    ("Missing Source Document", ("missing source document",)),
    ("Margin Threshold", ("minimum profit", "below margin")),
    ("Excluded Category", ("excluded category",)),
    ("Schedule Mapping", ("schedule", "mapping")),
    ("Pricing Validation", ("price", "pricing", "vat", "subtotal")),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _write_jsonl_records(path: Path, payloads: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for payload in payloads:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not path.exists():
        return items
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items


def list_fixture_paths(fixtures_dir: str | Path) -> List[Path]:
    root = Path(fixtures_dir)
    if not root.exists():
        return []
    return sorted(path for path in root.iterdir() if path.is_file() and path.suffix.lower() == ".json")


def resolve_tier_manifest_path(tier_label: str, manifests_dir: str | Path = DEFAULT_TIER_MANIFESTS_DIR) -> Path:
    slug = _safe_text(tier_label).lower().replace("-", "_").replace(" ", "_")
    return Path(manifests_dir) / f"{slug}.json"


def read_fixture_manifest(manifest_path: str | Path) -> Dict[str, Any]:
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"fixtures": payload if isinstance(payload, list) else []}


def load_fixture_manifest(manifest_path: str | Path) -> List[Path]:
    payload = read_fixture_manifest(manifest_path)
    raw_items = payload.get("fixtures") or []
    fixtures: List[Path] = []
    for raw in raw_items:
        if isinstance(raw, dict):
            candidate = raw.get("path")
        else:
            candidate = raw
        text = _safe_text(candidate)
        if text:
            fixtures.append(Path(text))
    return fixtures


def categorize_failure(result: Dict[str, Any]) -> str:
    blockers = result.get("blockers") if isinstance(result.get("blockers"), list) else []
    text = " | ".join(_safe_text(item).lower() for item in blockers if _safe_text(item))
    if not text:
        return "None" if result.get("passed") else "Unknown"
    for label, needles in FAILURE_CATEGORY_RULES:
        if any(needle in text for needle in needles):
            return label
    return "Other"


def compute_gate_score(result: Dict[str, Any]) -> float:
    quality_summary = result.get("quality_summary") if isinstance(result.get("quality_summary"), dict) else {}
    quote_pack = quality_summary.get("quote_pack") if isinstance(quality_summary.get("quote_pack"), dict) else {}
    quality_score = _safe_float(quote_pack.get("quality_score"))
    score = max(0.0, min(100.0, quality_score * 100.0))
    if not score and result.get("passed"):
        score = 100.0
    return round(score, 2)


def compute_confidence_score(result: Dict[str, Any], gate_score: Optional[float] = None) -> float:
    gate_score = compute_gate_score(result) if gate_score is None else gate_score
    signals = [
        gate_score,
        100.0 if bool(result.get("manual_submission_preserved")) else 0.0,
        100.0 if bool(result.get("persistence_verified")) else 0.0,
        100.0 if bool(result.get("audit_verified")) else 0.0,
    ]
    return round(sum(signals) / len(signals), 2)


def _normalize_expected_outcome(value: Any) -> str:
    outcome = _safe_text(value).lower()
    if outcome in {"pass", "passed", "success", "completed"}:
        return "pass"
    if outcome in {"refused", "reject", "rejected", "blocked"}:
        return "refused"
    return ""


def _actual_outcome(result: Dict[str, Any]) -> str:
    return "pass" if bool(result.get("passed")) else "refused"


def _consistency_matched(expected_outcome: str, result: Dict[str, Any]) -> bool:
    if not expected_outcome:
        return bool(result.get("passed"))
    return expected_outcome == _actual_outcome(result)


def summarize_fixture_result(
    fixture_path: str | Path,
    result: Dict[str, Any],
    *,
    manifest_entry: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    retries = int(result.get("retry_count") or result.get("retries") or 0)
    rollbacks = int(result.get("rollback_count") or result.get("rollbacks") or 0)
    expected_outcome = _normalize_expected_outcome((manifest_entry or {}).get("expected_outcome"))
    consistency_matched = _consistency_matched(expected_outcome, result)
    gate_score = compute_gate_score(result)
    confidence_score = compute_confidence_score(result, gate_score=gate_score)
    if consistency_matched and not result.get("passed") and expected_outcome == "refused":
        gate_score = 100.0
        confidence_score = 100.0
    failure_category = categorize_failure(result)
    return {
        "fixture": str(Path(fixture_path)),
        "tender_id": _safe_text(result.get("tender_id")) or Path(fixture_path).stem.upper(),
        "passed": bool(result.get("passed")),
        "expected_outcome": expected_outcome or ("pass" if bool(result.get("passed")) else ""),
        "actual_outcome": _actual_outcome(result),
        "consistency_matched": consistency_matched,
        "final_stage": _safe_text(result.get("final_stage")),
        "gate_score": gate_score,
        "confidence_score": confidence_score,
        "retry_count": retries,
        "rollback_count": rollbacks,
        "failure_category": failure_category,
        "blockers": list(result.get("blockers") or []),
        "production_ready": consistency_matched and gate_score >= 85.0 and confidence_score >= 85.0,
    }


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    return round(sum(items) / len(items), 2) if items else 0.0


def _production_ready_status(summary: Dict[str, Any]) -> str:
    if (
        _safe_float(summary.get("pass_rate")) >= 90.0
        and _safe_float(summary.get("gate_score")) >= 85.0
        and _safe_float(summary.get("confidence_score")) >= 85.0
        and _safe_float(summary.get("rollback_rate")) < 2.0
        and int(summary.get("critical_failures") or 0) == 0
    ):
        return "ready_for_stability_window"
    return "hold"


def _generated_sort_key(cycle: Dict[str, Any]) -> tuple[str, str]:
    return (_safe_text(cycle.get("generated_at")), _safe_text(cycle.get("run_id")))


def _cycle_identity_matches(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    return (
        _safe_text(left.get("tier_label")) == _safe_text(right.get("tier_label"))
        and _safe_text(left.get("week_ending")) == _safe_text(right.get("week_ending"))
        and _safe_text(left.get("cycle_label")) == _safe_text(right.get("cycle_label"))
    )


def normalize_dry_dispatch_registry() -> List[Dict[str, Any]]:
    items = _read_jsonl(DRY_DISPATCH_REGISTRY_FILE)
    if not items:
        return items
    normalized: List[Dict[str, Any]] = []
    changed = False
    for item in items:
        current = dict(item)
        if not _safe_text(current.get("run_id")):
            current["run_id"] = uuid4().hex
            changed = True
        if not _safe_text(current.get("run_status")):
            current["run_status"] = "active"
            changed = True
        if "superseded_by_run_id" not in current:
            current["superseded_by_run_id"] = ""
            changed = True
        if "corrects_run_id" not in current:
            current["corrects_run_id"] = ""
            changed = True
        normalized.append(current)

    groups: Dict[tuple[str, str, str], List[Dict[str, Any]]] = {}
    for item in normalized:
        key = (
            _safe_text(item.get("tier_label")),
            _safe_text(item.get("week_ending")),
            _safe_text(item.get("cycle_label")),
        )
        groups.setdefault(key, []).append(item)

    final_items: List[Dict[str, Any]] = []
    for group in groups.values():
        ordered = sorted(group, key=_generated_sort_key)
        active = ordered[-1]
        for item in ordered[:-1]:
            if item.get("run_status") != "superseded" or _safe_text(item.get("superseded_by_run_id")) != _safe_text(active.get("run_id")):
                item["run_status"] = "superseded"
                item["superseded_by_run_id"] = _safe_text(active.get("run_id"))
                if not _safe_text(item.get("superseded_at")):
                    item["superseded_at"] = _safe_text(active.get("corrected_at")) or _safe_text(active.get("generated_at")) or _now_iso()
                changed = True
            final_items.append(item)
        if active.get("run_status") != "active":
            active["run_status"] = "active"
            changed = True
        if _safe_text(active.get("superseded_by_run_id")):
            active["superseded_by_run_id"] = ""
            changed = True
        predecessor = ordered[-2] if len(ordered) > 1 else None
        predecessor_run_id = _safe_text(predecessor.get("run_id")) if predecessor else ""
        if predecessor_run_id and _safe_text(active.get("corrects_run_id")) != predecessor_run_id:
            active["corrects_run_id"] = predecessor_run_id
            changed = True
        final_items.append(active)

    final_items = sorted(final_items, key=_generated_sort_key)
    if changed:
        _write_jsonl_records(DRY_DISPATCH_REGISTRY_FILE, final_items)
        latest_active = [item for item in final_items if _safe_text(item.get("run_status")) == "active"]
        if latest_active:
            _write_json(LATEST_DRY_DISPATCH_REPORT_FILE, latest_active[-1])
    return final_items


def build_dry_dispatch_cycle(
    fixtures: Iterable[str | Path],
    *,
    tier_label: str,
    week_ending: Optional[str] = None,
    cycle_label: str = "weekly_dry_dispatch",
    manifest_metadata: Optional[Dict[str, Any]] = None,
    harness: Optional[E2ERFQHarness] = None,
) -> Dict[str, Any]:
    harness = harness or E2ERFQHarness()
    summaries: List[Dict[str, Any]] = []
    manifest_entries_by_path: Dict[str, Dict[str, Any]] = {}
    for raw in (manifest_metadata or {}).get("fixtures") or []:
        if isinstance(raw, dict):
            path_key = _safe_text(raw.get("path"))
            if path_key:
                manifest_entries_by_path[path_key] = raw
    for fixture in fixtures:
        result = harness.run_fixture(str(fixture))
        fixture_key = str(Path(fixture))
        summaries.append(
            summarize_fixture_result(
                fixture,
                result,
                manifest_entry=manifest_entries_by_path.get(fixture_key),
            )
        )

    total = len(summaries)
    passed = sum(1 for item in summaries if item.get("consistency_matched"))
    total_retries = sum(int(item.get("retry_count") or 0) for item in summaries)
    total_rollbacks = sum(int(item.get("rollback_count") or 0) for item in summaries)
    failed = [item for item in summaries if not item.get("consistency_matched")]
    failure_counts = Counter(item.get("failure_category") or "Unknown" for item in failed)
    top_failure_category = failure_counts.most_common(1)[0][0] if failure_counts else "None"
    summary = {
        "fixture_count": total,
        "pass_rate": round((passed / total) * 100.0, 2) if total else 0.0,
        "gate_score": _mean(float(item.get("gate_score") or 0.0) for item in summaries),
        "confidence_score": _mean(float(item.get("confidence_score") or 0.0) for item in summaries),
        "retry_rate": round((total_retries / total) * 100.0, 2) if total else 0.0,
        "rollback_rate": round((total_rollbacks / total) * 100.0, 2) if total else 0.0,
        "top_failure_category": top_failure_category,
        "critical_failures": len([item for item in failed if (item.get("failure_category") or "") in {"Missing Source Document", "Unknown"}]),
    }
    summary["production_ready_status"] = _production_ready_status(summary)

    return {
        "cycle_label": cycle_label,
        "run_id": "",
        "run_status": "pending",
        "superseded_by_run_id": "",
        "corrects_run_id": "",
        "tier_label": _safe_text(tier_label),
        "week_ending": _safe_text(week_ending) or date.today().isoformat(),
        "generated_at": _now_iso(),
        "manifest_metadata": manifest_metadata or {},
        "summary": summary,
        "defect_register": {
            "failure_counts": dict(sorted(failure_counts.items())),
            "top_failure_category": top_failure_category,
        },
        "fixtures": summaries,
    }


def append_dry_dispatch_cycle(cycle: Dict[str, Any]) -> Dict[str, Any]:
    existing = normalize_dry_dispatch_registry()
    run_id = _safe_text(cycle.get("run_id")) or uuid4().hex
    generated_at = _safe_text(cycle.get("generated_at")) or _now_iso()
    corrected_at = _now_iso()
    corrected = dict(cycle)
    corrected["run_id"] = run_id
    corrected["generated_at"] = generated_at
    corrected["run_status"] = "active"
    corrected["superseded_by_run_id"] = ""
    corrected["corrected_at"] = corrected_at

    corrected_run_id = ""
    updated_existing: List[Dict[str, Any]] = []
    for item in existing:
        current = dict(item)
        if _cycle_identity_matches(current, corrected) and _safe_text(current.get("run_status")) != "superseded":
            current["run_status"] = "superseded"
            current["superseded_by_run_id"] = run_id
            current["superseded_at"] = corrected_at
            if not corrected_run_id:
                corrected_run_id = _safe_text(current.get("run_id"))
        updated_existing.append(current)

    corrected["corrects_run_id"] = corrected_run_id
    updated_existing.append(corrected)
    _write_jsonl_records(DRY_DISPATCH_REGISTRY_FILE, updated_existing)
    _write_json(LATEST_DRY_DISPATCH_REPORT_FILE, corrected)
    return corrected


def read_dry_dispatch_cycles(limit: Optional[int] = None, *, include_superseded: bool = False) -> List[Dict[str, Any]]:
    items = normalize_dry_dispatch_registry()
    if not include_superseded:
        items = [item for item in items if _safe_text(item.get("run_status") or "active") != "superseded"]
    if limit is None:
        return items
    safe_limit = max(1, int(limit or 1))
    return items[-safe_limit:]


def evaluate_live_submission_gate(cycles: Optional[List[Dict[str, Any]]] = None, *, stable_weeks_required: int = 4) -> Dict[str, Any]:
    cycles = list(cycles if cycles is not None else read_dry_dispatch_cycles())
    recent = cycles[-max(1, int(stable_weeks_required or 4)) :]
    weekly_statuses = []
    stable = len(recent) >= stable_weeks_required
    qualifying_active_weeks = 0
    for cycle in recent:
        summary = cycle.get("summary") if isinstance(cycle.get("summary"), dict) else {}
        week_ok = (
            _safe_float(summary.get("pass_rate")) >= 90.0
            and _safe_float(summary.get("confidence_score")) >= 85.0
            and _safe_float(summary.get("gate_score")) >= 85.0
            and _safe_float(summary.get("rollback_rate")) < 2.0
            and int(summary.get("critical_failures") or 0) == 0
        )
        weekly_statuses.append(
            {
                "week_ending": cycle.get("week_ending"),
                "tier_label": cycle.get("tier_label"),
                "meets_gate": week_ok,
            }
        )
        if week_ok:
            qualifying_active_weeks += 1
        stable = stable and week_ok
    return {
        "status": "eligible_for_supervised_live" if stable else "hold",
        "stable_weeks_required": stable_weeks_required,
        "stable_weeks_observed": len(recent),
        "qualifying_active_weeks": qualifying_active_weeks,
        "qualifying_active_weeks_required": stable_weeks_required,
        "weekly_statuses": weekly_statuses,
        "requirements": {
            "pass_rate": ">=90%",
            "confidence_score": ">=85%",
            "gate_score": ">=85%",
            "rollback_rate": "<2%",
            "critical_failures": "0",
            "production_ready_status": f"stable {stable_weeks_required} weeks",
        },
    }
