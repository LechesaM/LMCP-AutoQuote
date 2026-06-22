from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.runtime_paths import get_runtime_paths


DEFAULT_INPUT_PATH = get_runtime_paths().runtime_root / "harvest_recovery" / "etenders_harvest_items.json"
DEFAULT_OUTPUT_DIR = get_runtime_paths().runtime_root / "harvest_recovery"
DEFAULT_DOC_PATH = get_runtime_paths().project_root / "docs" / "operations_validation_pack" / "sprint_8d_harvest_rejection_audit.md"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _clean(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _load_items(path: Path = DEFAULT_INPUT_PATH) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        rows = payload["items"]
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    return [row for row in rows if isinstance(row, dict)]


def _resolve_items_path(input_path: Optional[str], run_id: Optional[str]) -> Path:
    if input_path:
        return Path(input_path)
    if run_id:
        return get_runtime_paths().runtime_root / "harvest_recovery" / "runs" / run_id / "etenders_harvest_items.json"
    return DEFAULT_INPUT_PATH


def _normalize_reason(reason: Any) -> str:
    text = _clean(reason).lower()
    text = text.replace(" ", "_").replace("-", "_")
    return text


def _canonical_rejection_reason(reason: Any) -> str:
    text = _normalize_reason(reason)
    if not text:
        return ""
    if "supply" in text and "delivery" in text:
        return "not_supply_and_delivery"
    if "submission_route" in text or "submissionroute" in text or "valid_submission_route" in text:
        return "missing_submission_route"
    if "deadline" in text and ("missing" in text or "unclear" in text or "not_clearly" in text):
        return "missing_deadline"
    if "province" in text and ("unclear" in text or "confidently" in text):
        return "province_unclear"
    if "contract_value" in text and ("unclear" in text or "missing" in text):
        return "unclear_contract_value"
    if "profit" in text and ("unclear" in text or "missing" in text):
        return "unclear_profit_value"
    return text


def _derive_rejection_causes(qualification: Dict[str, Any]) -> List[str]:
    causes: List[str] = []
    if not qualification:
        return ["unknown_rejection_reason"]

    rejection_reasons = qualification.get("rejection_reasons") or []
    if isinstance(rejection_reasons, list):
        for reason in rejection_reasons:
            normalized = _canonical_rejection_reason(reason)
            if normalized and normalized not in causes:
                causes.append(normalized)

    if not causes:
        if not _bool(qualification.get("is_supply_delivery"), True):
            causes.append("not_supply_and_delivery")
        if _bool(qualification.get("excluded_by_business_rules"), False):
            causes.append("excluded_by_business_rules")
        if _bool(qualification.get("briefing_compulsory"), False):
            causes.append("compulsory_briefing")
        if not _bool(qualification.get("has_valid_submission_method"), True):
            causes.append("missing_submission_route")
        if _bool(qualification.get("estimated_profit_value") is not None, False) and not _bool(qualification.get("meets_profit_threshold"), True):
            causes.append("profit_below_threshold")
        if not _bool(qualification.get("province_ok"), True):
            causes.append("province_unclear")
        if qualification.get("estimated_contract_value") is None:
            causes.append("unclear_contract_value")
        if qualification.get("estimated_profit_value") is None:
            causes.append("unclear_profit_value")
        if qualification.get("days_to_deadline") is None:
            causes.append("missing_deadline")
    if not causes:
        causes.append("unknown_rejection_reason")
    return causes


def _derive_review_signals(qualification: Dict[str, Any]) -> List[str]:
    signals: List[str] = []
    if not qualification:
        return signals
    review_reasons = qualification.get("review_reasons") or []
    if isinstance(review_reasons, list):
        for reason in review_reasons:
            normalized = _canonical_rejection_reason(reason)
            if normalized and normalized not in signals:
                signals.append(normalized)
    return signals


def _acquisition_stage(acquisition: Dict[str, Any]) -> str:
    if not isinstance(acquisition, dict) or not acquisition:
        return "not_attempted"
    status = _clean(acquisition.get("status")).lower()
    if status in {"", "not_attempted"}:
        return "not_attempted"
    if status == "skipped":
        return "skipped"
    if status == "prepared":
        return "prepared"
    if status == "deferred":
        return "deferred"
    if status == "ok" and _to_int(acquisition.get("downloaded_count"), 0) > 0:
        return "succeeded"
    if status == "failed":
        return "failed"
    return "failed" if status else "not_attempted"


def _write_summary_md(path: Path, payload: Dict[str, Any]) -> None:
    metrics = payload["metrics"]
    lines: List[str] = [
        "# Sprint 8D eTenders Harvest Rejection Audit",
        "",
        f"Generated at: {payload['generated_at']}",
        "",
        "## Guardrails",
        "",
        f"- Portal submission disabled: `{payload['guardrails']['portal_submission_disabled']}`",
        f"- Human approval required: `{payload['guardrails']['human_approval_required']}`",
        f"- Autonomous submission enabled: `{payload['guardrails']['autonomous_submission_enabled']}`",
        "",
        "No source was disabled by this audit.",
        "",
        "## Funnel Separation",
        "",
        "| Stage | Count |",
        "| --- | ---: |",
        f"| Harvested items | {metrics['harvested_items']} |",
        f"| Persisted raw items | {metrics['persisted_raw_items']} |",
        f"| Qualified items | {metrics['qualified_items']} |",
        f"| Rejected items | {metrics['rejected_items']} |",
        f"| Acquisition skipped | {metrics['acquisition_skipped_items']} |",
        f"| Acquisition prepared | {metrics['acquisition_prepared_items']} |",
        f"| Acquisition deferred | {metrics['acquisition_deferred_items']} |",
        f"| Acquisition succeeded | {metrics['acquisition_succeeded_items']} |",
        f"| Acquisition failed | {metrics['acquisition_failed_items']} |",
        "",
        "## Rejection Causes",
        "",
        "| Cause | Count |",
        "| --- | ---: |",
    ]
    for cause, count in metrics["top_rejection_causes"]:
        lines.append(f"| {cause} | {count} |")
    if metrics.get("top_review_signals"):
        lines.extend(["", "## Review Signals", "", "| Signal | Count |", "| --- | ---: |"])
        for signal, count in metrics["top_review_signals"]:
            lines.append(f"| {signal} | {count} |")
    lines.extend(["", "## Top Rejected RFQs", "", "| RFQ ID | Buyer | Category | Causes | Acquisition |", "| --- | --- | --- | --- | --- |"])
    for row in payload["rejection_rows"][:20]:
        lines.append(
            f"| {row['rfq_id']} | {row['buyer_name']} | {row['category']} | {', '.join(row['rejection_causes'])} | {row['acquisition_stage']} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def audit_etenders_harvest_rejection(
    *,
    input_path: Path = DEFAULT_INPUT_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    items = _load_items(input_path)

    harvested_items = len(items)
    persisted_raw_items = sum(1 for item in items if isinstance(item.get("persist"), dict) and _bool(item["persist"].get("raw_upserted"), False))
    qualified_items = sum(1 for item in items if _bool((item.get("filtered") or {}).get("qualified"), False))
    rejected_items = sum(1 for item in items if _bool((item.get("filtered") or {}).get("rejected"), False))

    acquisition_stage_counts = Counter()
    rejection_cause_counts = Counter()
    review_signal_counts = Counter()
    rejection_rows: List[Dict[str, Any]] = []

    for item in items:
        filtered = item.get("filtered") if isinstance(item.get("filtered"), dict) else {}
        qualification = filtered.get("qualification_result") if isinstance(filtered.get("qualification_result"), dict) else {}
        if not qualification and isinstance(item.get("qualification"), dict):
            qualification = item["qualification"]
        acquisition = item.get("acquisition") if isinstance(item.get("acquisition"), dict) else {}
        acq_stage = _acquisition_stage(acquisition)
        acquisition_stage_counts[acq_stage] += 1
        if not _bool(filtered.get("rejected"), False):
            continue
        causes = _derive_rejection_causes(qualification or filtered)
        review_signals = _derive_review_signals(qualification or filtered)
        for cause in causes:
            rejection_cause_counts[cause] += 1
        for signal in review_signals:
            review_signal_counts[signal] += 1
        rejection_rows.append(
            {
                "rfq_id": _clean((item.get("raw_extracted") or {}).get("rfq_id") or item.get("identity", {}).get("rfq_id")),
                "buyer_name": _clean((item.get("raw_extracted") or {}).get("buyer_name") or item.get("identity", {}).get("buyer_name")),
                "category": _clean((item.get("raw_extracted") or {}).get("category")),
                "rejection_causes": causes,
                "review_signals": review_signals,
                "acquisition_stage": acq_stage,
                "qualification_status": _clean(qualification.get("qualification_status") or filtered.get("qualification_status")),
                "recommendation": _clean(filtered.get("recommendation")),
            }
        )

    metrics = {
        "input_items": len(items),
        "harvested_items": harvested_items,
        "persisted_raw_items": persisted_raw_items,
        "qualified_items": qualified_items,
        "rejected_items": rejected_items,
        "acquisition_skipped_items": acquisition_stage_counts.get("skipped", 0),
        "acquisition_prepared_items": acquisition_stage_counts.get("prepared", 0),
        "acquisition_deferred_items": acquisition_stage_counts.get("deferred", 0),
        "acquisition_succeeded_items": acquisition_stage_counts.get("succeeded", 0),
        "acquisition_failed_items": acquisition_stage_counts.get("failed", 0),
        "acquisition_not_attempted_items": acquisition_stage_counts.get("not_attempted", 0),
        "top_rejection_causes": rejection_cause_counts.most_common(),
        "top_review_signals": review_signal_counts.most_common(),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "etenders_harvest_rejection_audit.json"
    md_path = output_dir / "etenders_harvest_rejection_audit.md"

    payload = {
        "status": "ok",
        "generated_at": _now_iso(),
        "input_path": str(input_path),
        "guardrails": {
            "portal_submission_disabled": True,
            "human_approval_required": True,
            "autonomous_submission_enabled": False,
        },
        "metrics": metrics,
        "rejection_rows": rejection_rows,
        "scope": {
            "sprint": "Sprint 8D",
            "focus": "Separate Harvest from Document Acquisition",
            "notes": "Audit why harvested RFQs were rejected before document acquisition was allowed to proceed.",
        },
    }

    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_summary_md(md_path, payload)

    docs_path = DEFAULT_DOC_PATH
    docs_path.write_text(
        "\n".join(
            [
                "# Sprint 8D Harvest Rejection Audit",
                "",
                "Sprint 8D separates harvest from document acquisition and audits why harvested RFQs were rejected before acquisition.",
                "",
                f"- Input: `{input_path}`",
                f"- Output JSON: `{json_path}`",
                f"- Output Markdown: `{md_path}`",
                "",
                "No source was disabled by this audit.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "payload": payload,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "docs_path": str(docs_path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sprint 8D eTenders Harvest Rejection Audit")
    parser.add_argument("--input-path", "--items", dest="input_path", type=str, default="", help="Input harvest items JSON")
    parser.add_argument("--run-id", type=str, default="", help="Optional run identifier to resolve a preserved run-scoped items file")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Output directory for audit artifacts")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    input_path = _resolve_items_path(args.input_path, args.run_id)
    audit_etenders_harvest_rejection(
        input_path=input_path,
        output_dir=Path(args.output_dir),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
