from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple


HISTORY_PATH = Path("runtime/submission_history/submission_history.json")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _extract_financials(pack: Dict[str, Any]) -> Tuple[float, float, float, float]:
    financials = _safe_dict(pack.get("financials"))
    totals = _safe_dict(pack.get("totals"))
    summary = _safe_dict(pack.get("summary"))
    pricing = _safe_dict(pack.get("pricing"))

    estimated_revenue = (
        _safe_float(financials.get("estimated_revenue"))
        or _safe_float(totals.get("estimated_revenue"))
        or _safe_float(summary.get("estimated_revenue"))
        or _safe_float(pricing.get("estimated_revenue"))
        or _safe_float(totals.get("total_incl_vat"))
        or _safe_float(totals.get("total_including_vat"))
        or _safe_float(summary.get("grand_total"))
        or _safe_float(summary.get("total_including_vat"))
    )

    estimated_cost = (
        _safe_float(financials.get("estimated_cost"))
        or _safe_float(totals.get("estimated_cost"))
        or _safe_float(summary.get("estimated_cost"))
        or _safe_float(pricing.get("estimated_cost"))
        or _safe_float(pricing.get("cost_total"))
        or _safe_float(summary.get("cost_total"))
    )

    estimated_profit = (
        _safe_float(financials.get("estimated_profit"))
        or _safe_float(totals.get("estimated_profit"))
        or _safe_float(summary.get("estimated_profit"))
        or _safe_float(pricing.get("estimated_profit"))
    )

    estimated_margin = (
        _safe_float(financials.get("estimated_margin"))
        or _safe_float(totals.get("estimated_margin"))
        or _safe_float(summary.get("estimated_margin"))
        or _safe_float(pricing.get("estimated_margin"))
    )

    if estimated_profit <= 0 and estimated_revenue > 0 and estimated_cost > 0:
        estimated_profit = round(estimated_revenue - estimated_cost, 2)

    if estimated_cost <= 0 and estimated_revenue > 0 and estimated_profit > 0:
        estimated_cost = round(estimated_revenue - estimated_profit, 2)

    if estimated_margin <= 0 and estimated_revenue > 0 and estimated_profit > 0:
        estimated_margin = round(estimated_profit / estimated_revenue, 4)

    return (
        round(estimated_revenue, 2),
        round(estimated_cost, 2),
        round(estimated_profit, 2),
        round(estimated_margin, 4),
    )


def _resolve_quote_pack_path(record: Dict[str, Any]) -> Path | None:
    raw_result = _safe_dict(record.get("raw_result"))
    metadata = _safe_dict(record.get("metadata"))

    candidates = [
        raw_result.get("quote_pack_metadata_path"),
        metadata.get("quote_pack_metadata_path"),
    ]

    quote_folder = (
        raw_result.get("quote_folder")
        or metadata.get("quote_folder")
        or raw_result.get("quote_pack_dir")
        or metadata.get("quote_pack_dir")
    )
    buyer_rfq_number = record.get("buyer_rfq_number") or raw_result.get("buyer_rfq_number")
    quote_number = record.get("quote_number") or raw_result.get("quote_number")

    if quote_folder and buyer_rfq_number and quote_number:
        candidates.append(
            f"{quote_folder}/{buyer_rfq_number}__{quote_number}__quote_pack.json"
        )

    for candidate in candidates:
        if not candidate:
            continue
        text = str(candidate).strip()
        if not text:
            continue

        normalized = text
        if normalized.startswith("/app/"):
            normalized = normalized.replace("/app/", "", 1)

        path = Path(normalized)
        if path.exists() and path.is_file():
            return path

    return None


def main() -> None:
    if not HISTORY_PATH.exists():
        raise SystemExit(f"History file not found: {HISTORY_PATH}")

    data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("Submission history JSON is not a list.")

    updated = 0
    skipped = 0

    for record in data:
        if not isinstance(record, dict):
            skipped += 1
            continue

        raw_result = _safe_dict(record.get("raw_result"))
        metadata = _safe_dict(record.get("metadata"))

        existing_profit = (
            _safe_float(raw_result.get("estimated_profit"))
            or _safe_float(metadata.get("estimated_profit"))
        )
        existing_revenue = (
            _safe_float(raw_result.get("estimated_revenue"))
            or _safe_float(metadata.get("estimated_revenue"))
        )

        if existing_profit > 0 and existing_revenue > 0:
            skipped += 1
            continue

        pack_path = _resolve_quote_pack_path(record)
        if pack_path is None:
            skipped += 1
            continue

        try:
            pack = json.loads(pack_path.read_text(encoding="utf-8"))
        except Exception:
            skipped += 1
            continue

        if not isinstance(pack, dict):
            skipped += 1
            continue

        estimated_revenue, estimated_cost, estimated_profit, estimated_margin = _extract_financials(pack)

        if estimated_revenue <= 0:
            skipped += 1
            continue

        raw_result["estimated_revenue"] = estimated_revenue
        raw_result["estimated_cost"] = estimated_cost
        raw_result["estimated_profit"] = estimated_profit
        raw_result["estimated_margin"] = estimated_margin
        raw_result["quote_pack_metadata_path"] = raw_result.get("quote_pack_metadata_path") or str(pack_path)

        metadata["estimated_revenue"] = estimated_revenue
        metadata["estimated_cost"] = estimated_cost
        metadata["estimated_profit"] = estimated_profit
        metadata["estimated_margin"] = estimated_margin
        metadata["quote_pack_metadata_path"] = metadata.get("quote_pack_metadata_path") or str(pack_path)

        record["raw_result"] = raw_result
        record["metadata"] = metadata
        updated += 1

    HISTORY_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print({
        "status": "ok",
        "updated": updated,
        "skipped": skipped,
        "history_file": str(HISTORY_PATH),
    })


if __name__ == "__main__":
    main()
