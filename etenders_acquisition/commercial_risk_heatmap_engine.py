#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

SUBMISSION_FILE = (
    RUNTIME_DIR
    / "submission_pack"
    / "final_submission_pricing_schedule.json"
)

OUT_DIR = RUNTIME_DIR / "commercial_risk_heatmap"

HEATMAP_FILE = OUT_DIR / "commercial_risk_heatmap.json"
SUMMARY_FILE = OUT_DIR / "commercial_risk_heatmap_summary.json"
CATEGORY_RISK_FILE = OUT_DIR / "category_risk_analysis.json"
SUPPLIER_RISK_FILE = OUT_DIR / "supplier_risk_analysis.json"


HIGH_RISK_KEYWORDS = [
    "bearing",
    "pump",
    "motor",
    "coupling",
    "electrical",
    "transformer",
    "bitumen",
    "tack coat",
    "prime coat",
]

LOW_CONFIDENCE_TYPES = [
    "LOW",
    "FALLBACK_LOW",
]


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


def keyword_risk(description):
    d = (description or "").lower()

    matched = []

    for kw in HIGH_RISK_KEYWORDS:
        if kw in d:
            matched.append(kw)

    return matched


def line_risk_score(line):
    score = 0
    flags = []

    total = money(line.get("submission_total"))
    confidence = line.get("confidence")
    band = line.get("win_probability_band")
    margin = money(line.get("margin_pct"))

    if confidence in LOW_CONFIDENCE_TYPES:
        score += 30
        flags.append("low_confidence")

    if band == "LOW":
        score += 20
        flags.append("low_win_probability")

    if total > 250000:
        score += 15
        flags.append("high_value_line")

    if margin < 10:
        score += 20
        flags.append("thin_margin")

    keyword_flags = keyword_risk(line.get("description"))

    if keyword_flags:
        score += 10
        flags.append("technical_specialist")

    if margin > 30:
        score += 10
        flags.append("high_margin_review")

    if total > 1000000:
        score += 20
        flags.append("major_value_exposure")

    score = min(score, 100)

    if score >= 70:
        level = "CRITICAL"
    elif score >= 50:
        level = "HIGH"
    elif score >= 30:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "risk_score": score,
        "risk_level": level,
        "risk_flags": flags,
        "keyword_flags": keyword_flags,
    }


def category_analysis(lines):
    grouped = defaultdict(list)

    for line in lines:
        grouped[line.get("category") or "unknown"].append(line)

    result = {}

    for category, items in grouped.items():
        total_value = money(sum(
            money(x.get("submission_total")) for x in items
        ))

        avg_margin = round(
            sum(money(x.get("margin_pct")) for x in items)
            / max(len(items), 1),
            2
        )

        low_conf = sum(
            1 for x in items
            if x.get("confidence") in LOW_CONFIDENCE_TYPES
        )

        high_risk = sum(
            1 for x in items
            if x.get("risk_level") in ["HIGH", "CRITICAL"]
        )

        result[category] = {
            "line_count": len(items),
            "total_value": total_value,
            "average_margin_pct": avg_margin,
            "low_confidence_lines": low_conf,
            "high_risk_lines": high_risk,
        }

    return result


def supplier_exposure(lines):
    supplier_map = defaultdict(lambda: {
        "line_count": 0,
        "total_value": 0,
    })

    for line in lines:
        desc = (line.get("description") or "").upper()

        supplier = "UNKNOWN"

        if "SKF" in desc:
            supplier = "SKF"

        elif "ABB" in desc:
            supplier = "ABB"

        elif "LINATEX" in desc:
            supplier = "LINATEX"

        elif "RS" in desc:
            supplier = "RS"

        supplier_map[supplier]["line_count"] += 1
        supplier_map[supplier]["total_value"] += money(
            line.get("submission_total")
        )

    return supplier_map


def main():
    data = load_json(SUBMISSION_FILE, default={})

    pricing_lines = data.get("pricing_schedule", [])

    analyzed = []

    for line in pricing_lines:
        risk = line_risk_score(line)

        merged = dict(line)
        merged.update(risk)

        analyzed.append(merged)

    total_value = money(sum(
        money(x.get("submission_total")) for x in analyzed
    ))

    risk_counts = Counter(x["risk_level"] for x in analyzed)

    category_risk = category_analysis(analyzed)

    supplier_risk = supplier_exposure(analyzed)

    highest_risk = sorted(
        analyzed,
        key=lambda x: x["risk_score"],
        reverse=True
    )[:250]

    summary = {
        "generated_at": now_iso(),
        "lines_analyzed": len(analyzed),
        "portfolio_submission_value": total_value,
        "risk_counts": dict(risk_counts),
        "critical_lines": risk_counts.get("CRITICAL", 0),
        "high_risk_lines": risk_counts.get("HIGH", 0),
        "medium_risk_lines": risk_counts.get("MEDIUM", 0),
        "low_risk_lines": risk_counts.get("LOW", 0),
    }

    heatmap_output = {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "highest_risk_lines": highest_risk,
        "all_lines": analyzed,
    }

    write_json(HEATMAP_FILE, heatmap_output)
    write_json(SUMMARY_FILE, summary)
    write_json(CATEGORY_RISK_FILE, category_risk)
    write_json(SUPPLIER_RISK_FILE, supplier_risk)

    print(f"Heatmap written: {HEATMAP_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Category risk written: {CATEGORY_RISK_FILE}")
    print(f"Supplier risk written: {SUPPLIER_RISK_FILE}")

    print(f"Lines analyzed: {summary['lines_analyzed']}")
    print(f"Portfolio value: R{summary['portfolio_submission_value']:,.2f}")

    print("\nRisk counts:")
    for k, v in risk_counts.items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
