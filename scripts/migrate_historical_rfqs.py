from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from app.services.rfq_archive_service import CLASSIFICATION_REVIEW_FILE, HISTORICAL_RFQ_FILE
from app.services.rfq_operational_classification_service import (
    CLASSIFICATION_VERSION,
    RfqOperationalClassification,
    RfqOperationalClassificationService,
    canonical_rfq_id,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LIVE_RFQ_STORE = PROJECT_ROOT / "runtime" / "live_rfqs.json"
LIFECYCLE_RFQ_STORE = PROJECT_ROOT / "runtime" / "rfq_lifecycle" / "rfqs.json"
DEFAULT_JSON_REPORT = Path("/tmp/lmcp-rfq-classification-preview.json")
DEFAULT_CSV_REPORT = Path("/tmp/lmcp-rfq-classification-preview.csv")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_items(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("items"), list):
            return [item for item in payload["items"] if isinstance(item, dict)]
        if isinstance(payload.get("items"), dict):
            return [item for item in payload["items"].values() if isinstance(item, dict)]
        if isinstance(payload.get("rfqs"), list):
            return [item for item in payload["rfqs"] if isinstance(item, dict)]
    return []


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except Exception:
        return str(path)


def discover_records(
    live_store: Path = LIVE_RFQ_STORE,
    lifecycle_store: Path = LIFECYCLE_RFQ_STORE,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    sources: List[Dict[str, Any]] = []
    records: List[Dict[str, Any]] = []
    for path in (live_store, lifecycle_store):
        rows = _extract_items(_read_json(path))
        source_name = _display_path(path)
        sources.append({"path": source_name, "count": len(rows)})
        for row in rows:
            record = dict(row)
            record.setdefault("_source_stores", [source_name])
            records.append(record)
    return records, sources


def classify_records(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    classifier = RfqOperationalClassificationService()
    buckets = {"ACTIVE": [], "HISTORICAL": [], "REVIEW_REQUIRED": []}
    rows = []
    duplicate_counts = Counter(canonical_rfq_id(record) for record in records)
    for record in records:
        result = classifier.classify(record)
        key = canonical_rfq_id(record)
        row = {
            "rfq_id": key,
            "buyer": record.get("buyer_name") or record.get("buyer") or record.get("department") or "",
            "title": record.get("title") or record.get("description") or "",
            "source": record.get("source") or record.get("source_name") or "",
            "raw_status": record.get("status") or record.get("current_state") or record.get("submission_status") or "",
            "raw_closing_date": record.get("closing_date") or record.get("closing_at") or record.get("deadline") or "",
            "classification": result.classification.value,
            "reason": result.reason,
            "normalized_closing_at": result.normalized_closing_at.isoformat() if result.normalized_closing_at else "",
            "confidence": result.confidence,
            "source_stores": ";".join(record.get("_source_stores") or []),
            "duplicate_count": max(0, duplicate_counts[key] - 1),
        }
        buckets[result.classification.value].append(record)
        rows.append(row)

    all_ids = {row["rfq_id"] for row in rows}
    bucket_ids = {
        name: {canonical_rfq_id(record) for record in bucket}
        for name, bucket in buckets.items()
    }
    union = set().union(*bucket_ids.values())
    intersections = {
        "ACTIVE_HISTORICAL": sorted(bucket_ids["ACTIVE"] & bucket_ids["HISTORICAL"]),
        "ACTIVE_REVIEW_REQUIRED": sorted(bucket_ids["ACTIVE"] & bucket_ids["REVIEW_REQUIRED"]),
        "HISTORICAL_REVIEW_REQUIRED": sorted(bucket_ids["HISTORICAL"] & bucket_ids["REVIEW_REQUIRED"]),
    }
    reasons = Counter(row["reason"] for row in rows)
    return {
        "generated_at": _now_iso(),
        "classification_version": CLASSIFICATION_VERSION,
        "dry_run": True,
        "counts": {
            "total": len(rows),
            "active": len(buckets["ACTIVE"]),
            "historical": len(buckets["HISTORICAL"]),
            "review_required": len(buckets["REVIEW_REQUIRED"]),
            "missing_closing_date": reasons.get("MISSING_CLOSING_DATE", 0),
            "invalid_closing_date": reasons.get("INVALID_CLOSING_DATE", 0),
            "duplicate_canonical_ids": sum(1 for count in duplicate_counts.values() if count > 1),
        },
        "reasons": dict(sorted(reasons.items())),
        "union_verified": all_ids == union,
        "intersections_empty": all(not values for values in intersections.values()),
        "intersections": intersections,
        "rows": rows,
        "buckets": buckets,
    }


def _write_json_report(report: Dict[str, Any], path: Path) -> None:
    serializable = {k: v for k, v in report.items() if k != "buckets"}
    path.write_text(json.dumps(serializable, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")


def _write_csv_report(report: Dict[str, Any], path: Path) -> None:
    rows = report.get("rows", [])
    fieldnames = [
        "rfq_id",
        "buyer",
        "title",
        "source",
        "raw_status",
        "raw_closing_date",
        "classification",
        "reason",
        "normalized_closing_at",
        "confidence",
        "source_stores",
        "duplicate_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _atomic_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def apply_migration(
    report: Dict[str, Any],
    backup_dir: Path,
    *,
    live_store: Path = LIVE_RFQ_STORE,
    historical_file: Path = HISTORICAL_RFQ_FILE,
    review_file: Path = CLASSIFICATION_REVIEW_FILE,
) -> Dict[str, Any]:
    if not report.get("union_verified") or not report.get("intersections_empty"):
        raise RuntimeError("Refusing apply: classification reconciliation failed")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_backup = backup_dir / f"rfq-classification-{stamp}"
    run_backup.mkdir(parents=True, exist_ok=False)
    for path in (live_store, historical_file, review_file):
        if path.exists():
            shutil.copy2(path, run_backup / path.name)

    active = report["buckets"][RfqOperationalClassification.ACTIVE.value]
    historical = report["buckets"][RfqOperationalClassification.HISTORICAL.value]
    review = report["buckets"][RfqOperationalClassification.REVIEW_REQUIRED.value]
    _atomic_write(
        historical_file,
        {"version": "rfq_archive_v1", "updated_at": _now_iso(), "items": {canonical_rfq_id(row): row for row in historical}},
    )
    _atomic_write(
        review_file,
        {"version": "rfq_classification_review_v1", "updated_at": _now_iso(), "items": {canonical_rfq_id(row): row for row in review}},
    )
    _atomic_write(
        live_store,
        {"status": "ok", "updated_at": _now_iso(), "count": len(active), "items": active},
    )
    return {"status": "ok", "backup_dir": str(run_backup), "active": len(active), "historical": len(historical), "review_required": len(review)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify active, historical, and review-required RFQs.")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--json-report", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument("--csv-report", type=Path, default=DEFAULT_CSV_REPORT)
    parser.add_argument("--live-store", type=Path, default=LIVE_RFQ_STORE)
    parser.add_argument("--lifecycle-store", type=Path, default=LIFECYCLE_RFQ_STORE)
    parser.add_argument("--historical-store", type=Path, default=HISTORICAL_RFQ_FILE)
    parser.add_argument("--review-store", type=Path, default=CLASSIFICATION_REVIEW_FILE)
    args = parser.parse_args()

    records, sources = discover_records(args.live_store, args.lifecycle_store)
    report = classify_records(records)
    report["source_stores"] = sources
    report["dry_run"] = not args.apply
    _write_json_report(report, args.json_report)
    _write_csv_report(report, args.csv_report)

    apply_result = None
    if args.apply:
        if not args.backup_dir or not args.backup_dir.is_absolute():
            raise SystemExit("--apply requires --backup-dir with an absolute path")
        apply_result = apply_migration(
            report,
            args.backup_dir,
            live_store=args.live_store,
            historical_file=args.historical_store,
            review_file=args.review_store,
        )

    print(
        json.dumps(
            {
                "status": "ok",
                "dry_run": not args.apply,
                "json_report": str(args.json_report),
                "csv_report": str(args.csv_report),
                "counts": report["counts"],
                "reasons": report["reasons"],
                "union_verified": report["union_verified"],
                "intersections_empty": report["intersections_empty"],
                "apply_result": apply_result,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
