#!/usr/bin/env python3
import csv
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

OPTIMIZED_FILE = (
    RUNTIME_DIR
    / "commercial_intelligence"
    / "dynamic_margin_optimized_bid.json"
)

WIN_FILE = (
    RUNTIME_DIR
    / "commercial_intelligence"
    / "bid_win_probability_analysis.json"
)

OUT_DIR = RUNTIME_DIR / "submission_pack"

EXEC_SUMMARY_FILE = OUT_DIR / "executive_commercial_summary.json"
PRICING_JSON_FILE = OUT_DIR / "final_submission_pricing_schedule.json"
PRICING_CSV_FILE = OUT_DIR / "final_submission_pricing_schedule.csv"
RISK_REPORT_FILE = OUT_DIR / "commercial_risk_report.json"
SUMMARY_FILE = OUT_DIR / "submission_pack_summary.json"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def money(v):
    try:
        return round(float(v or 0), 2)
    except Exception:
        return 0.0


def load_json(path, default=None):
    if default is None:
        default = {}

    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_win_lookup(win_data):
    lookup = {}

    for line in win_data.get("line_analysis", []):
        lookup[int(line.get("line_no") or 0)] = line

    return lookup


def compile_submission_line(line, win):
    return {
        "line_no": line.get("line_no"),
        "description": line.get("description"),
        "category": line.get("category"),
        "quantity": line.get("quantity"),
        "unit": line.get("unit"),
        "cost_unit_rate": line.get("cost_unit_rate"),
        "cost_total": line.get("cost_total"),
        "submission_unit_rate": line.get("optimized_unit_rate"),
        "submission_total": line.get("optimized_bid_total"),
        "gross_profit": line.get("optimized_gross_profit"),
        "margin_pct": line.get("optimized_margin_pct"),
        "confidence": line.get("source_confidence"),
        "win_probability_score": line.get("win_probability_score"),
        "win_probability_band": line.get("win_probability_band"),
        "market_position": line.get("market_position"),
        "risk_flags": line.get("risk_flags", []),
        "optimization_reasons": line.get("optimization_reasons", []),
        "recommended_action": recommend_action(line, win),
    }


def recommend_action(line, win):
    band = (win or {}).get("win_probability_band") or line.get("win_probability_band")
    flags = (win or {}).get("risk_flags") or line.get("risk_flags") or []
    margin = money(line.get("optimized_margin_pct"))

    if "below_cost" in flags:
        return "DO_NOT_SUBMIT"

    if band == "LOW" and margin <= 10:
        return "SUBMIT_AGGRESSIVE"

    if band in ["VERY_HIGH", "HIGH"]:
        return "SUBMIT_CONFIDENT"

    if band == "LOW":
        return "REVIEW_PRICE"

    return "SUBMIT_STANDARD"


def write_csv(path, rows):
    fields = [
        "line_no",
        "description",
        "category",
        "quantity",
        "unit",
        "cost_unit_rate",
        "cost_total",
        "submission_unit_rate",
        "submission_total",
        "gross_profit",
        "margin_pct",
        "confidence",
        "win_probability_score",
        "win_probability_band",
        "market_position",
        "recommended_action",
        "risk_flags",
        "optimization_reasons",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for row in rows:
            r = dict(row)
            r["risk_flags"] = ",".join(r.get("risk_flags") or [])
            r["optimization_reasons"] = ",".join(r.get("optimization_reasons") or [])
            writer.writerow(r)


def main():
    optimized_data = load_json(OPTIMIZED_FILE, default={})
    win_data = load_json(WIN_FILE, default={})

    optimized_lines = optimized_data.get("optimized_lines", [])
    win_lookup = build_win_lookup(win_data)

    submission_lines = []

    for line in optimized_lines:
        line_no = int(line.get("line_no") or 0)
        submission_lines.append(
            compile_submission_line(line, win_lookup.get(line_no))
        )

    total_cost = money(sum(x["cost_total"] for x in submission_lines))
    total_submission = money(sum(x["submission_total"] for x in submission_lines))
    total_profit = money(sum(x["gross_profit"] for x in submission_lines))

    avg_margin = round((total_profit / total_submission) * 100, 2) if total_submission else 0

    category_counts = Counter(x["category"] or "unknown" for x in submission_lines)
    action_counts = Counter(x["recommended_action"] for x in submission_lines)
    win_band_counts = Counter(x["win_probability_band"] or "unknown" for x in submission_lines)
    confidence_counts = Counter(x["confidence"] or "unknown" for x in submission_lines)

    risk_counter = Counter()
    for line in submission_lines:
        for flag in line.get("risk_flags", []):
            risk_counter[flag] += 1

    executive_summary = {
        "generated_at": now_iso(),
        "submission_status": "READY_FOR_REVIEW",
        "total_lines": len(submission_lines),
        "total_cost_value": total_cost,
        "final_submission_value": total_submission,
        "projected_gross_profit": total_profit,
        "average_margin_pct": avg_margin,
        "portfolio_win_band": win_data.get("summary", {}).get("portfolio_win_band"),
        "average_win_probability_score": win_data.get("summary", {}).get(
            "average_win_probability_score"
        ),
        "expected_profit_value": win_data.get("summary", {}).get(
            "portfolio_expected_profit"
        ),
        "category_counts": dict(category_counts),
        "recommended_action_counts": dict(action_counts),
        "win_band_counts": dict(win_band_counts),
        "confidence_counts": dict(confidence_counts),
    }

    risk_report = {
        "generated_at": executive_summary["generated_at"],
        "risk_counts": dict(risk_counter),
        "review_lines": [
            x for x in submission_lines
            if x["recommended_action"] in ["REVIEW_PRICE", "DO_NOT_SUBMIT"]
        ][:500],
    }

    pricing_output = {
        "generated_at": executive_summary["generated_at"],
        "summary": executive_summary,
        "pricing_schedule": submission_lines,
    }

    write_json(EXEC_SUMMARY_FILE, executive_summary)
    write_json(PRICING_JSON_FILE, pricing_output)
    write_json(RISK_REPORT_FILE, risk_report)
    write_json(SUMMARY_FILE, executive_summary)
    write_csv(PRICING_CSV_FILE, submission_lines)

    print(f"Executive summary written: {EXEC_SUMMARY_FILE}")
    print(f"Final pricing JSON written: {PRICING_JSON_FILE}")
    print(f"Final pricing CSV written: {PRICING_CSV_FILE}")
    print(f"Risk report written: {RISK_REPORT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")

    print(f"Lines: {executive_summary['total_lines']}")
    print(f"Final submission value: R{executive_summary['final_submission_value']:,.2f}")
    print(f"Projected profit: R{executive_summary['projected_gross_profit']:,.2f}")
    print(f"Average margin: {executive_summary['average_margin_pct']}%")
    print(f"Portfolio win band: {executive_summary['portfolio_win_band']}")


if __name__ == "__main__":
    main()
