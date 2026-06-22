#!/usr/bin/env python3
import csv
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

HEATMAP_FILE = (
    RUNTIME_DIR
    / "commercial_risk_heatmap"
    / "commercial_risk_heatmap.json"
)

CATEGORY_RISK_FILE = (
    RUNTIME_DIR
    / "commercial_risk_heatmap"
    / "category_risk_analysis.json"
)

SUBMISSION_FILE = (
    RUNTIME_DIR
    / "submission_pack"
    / "final_submission_pricing_schedule.json"
)

OUT_DIR = RUNTIME_DIR / "bid_defense"

DEFENSE_JSON = OUT_DIR / "intelligent_bid_defense_report.json"
DEFENSE_CSV = OUT_DIR / "bid_defense_notes.csv"
ASSUMPTIONS_FILE = OUT_DIR / "assumptions_and_qualifications.json"
NEGOTIATION_FILE = OUT_DIR / "procurement_negotiation_guidance.json"
SUMMARY_FILE = OUT_DIR / "bid_defense_summary.json"


VOLATILE_KEYWORDS = [
    "bitumen",
    "asphalt",
    "tack coat",
    "prime coat",
    "steel",
    "leather",
    "shoe",
    "glove",
    "ppe",
    "fuel",
    "copper",
    "rubber",
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


def contains_any(description, words):
    d = str(description or "").lower()
    return [w for w in words if w in d]


def defense_note(line):
    category = line.get("category")
    desc = line.get("description")
    risk_level = line.get("risk_level")
    flags = line.get("risk_flags", [])
    confidence = line.get("confidence")
    total = money(line.get("submission_total"))
    margin = money(line.get("margin_pct"))
    volatility = contains_any(desc, VOLATILE_KEYWORDS)

    notes = []

    if confidence in ["FALLBACK_LOW", "LOW"]:
        notes.append(
            "Pricing is based on fallback or low-confidence historical intelligence and should be validated with supplier quotations before final submission."
        )

    if "major_value_exposure" in flags:
        notes.append(
            "Line carries major value exposure and should receive senior commercial review."
        )

    if "technical_specialist" in flags:
        notes.append(
            "Technical/specialist item; pricing should be supported by supplier/OEM confirmation and specification compliance check."
        )

    if volatility:
        notes.append(
            "Item is exposed to commodity/market volatility: "
            + ", ".join(volatility)
            + ". Rate validity and escalation assumptions should be confirmed."
        )

    if margin < 10:
        notes.append(
            "Margin is thin. Confirm that logistics, escalation, finance costs, and wastage are fully covered."
        )

    if risk_level in ["CRITICAL", "HIGH"]:
        notes.append(
            "Recommended action: obtain supplier quote, verify quantity/unit, and approve rate before bid submission."
        )

    if not notes:
        notes.append(
            "No exceptional commercial defense required; maintain standard pricing record and supplier backup."
        )

    return " ".join(notes)


def commercial_assumption(line):
    category = line.get("category")
    desc = line.get("description")
    confidence = line.get("confidence")
    flags = line.get("risk_flags", [])

    assumptions = []

    if confidence in ["FALLBACK_LOW", "LOW"]:
        assumptions.append(
            "Rate is subject to supplier confirmation and may require adjustment before award."
        )

    if category in ["building_material", "ppe", "mechanical"]:
        assumptions.append(
            "Rate assumes current market availability and normal delivery lead times."
        )

    if "major_value_exposure" in flags:
        assumptions.append(
            "High-value line assumes no material scope change, quantity change, or specification substitution."
        )

    if contains_any(desc, VOLATILE_KEYWORDS):
        assumptions.append(
            "Rate excludes abnormal market escalation beyond supplier validity period unless separately allowed."
        )

    return assumptions


def negotiation_guidance(line):
    category = line.get("category")
    total = money(line.get("submission_total"))
    confidence = line.get("confidence")
    flags = line.get("risk_flags", [])

    priority = "LOW"
    actions = []

    if total > 1000000 or "major_value_exposure" in flags:
        priority = "CRITICAL"
        actions.append("Request firm supplier quote and validity period.")
        actions.append("Negotiate volume discount and delivery schedule.")
        actions.append("Check alternative suppliers or equivalent products.")

    elif total > 250000:
        priority = "HIGH"
        actions.append("Obtain at least two supplier confirmations.")
        actions.append("Negotiate improved rate before submission.")

    elif confidence in ["FALLBACK_LOW", "LOW"]:
        priority = "MEDIUM"
        actions.append("Validate fallback rate against supplier quotation.")

    else:
        actions.append("Standard procurement follow-up only.")

    if category == "ppe":
        actions.append("Confirm compliance with SANS/specification requirements.")
    elif category == "building_material":
        actions.append("Confirm transport, wastage, and escalation assumptions.")
    elif category == "mechanical":
        actions.append("Confirm OEM/part-number compatibility.")

    return {
        "priority": priority,
        "actions": actions,
    }


def build_reports():
    heatmap = load_json(HEATMAP_FILE, default={})
    category_risk = load_json(CATEGORY_RISK_FILE, default={})
    submission = load_json(SUBMISSION_FILE, default={})

    all_lines = heatmap.get("all_lines", [])
    highest_risk = heatmap.get("highest_risk_lines", [])

    defense_lines = []

    for line in all_lines:
        note = defense_note(line)
        assumptions = commercial_assumption(line)
        guidance = negotiation_guidance(line)

        defense_lines.append({
            "line_no": line.get("line_no"),
            "risk_level": line.get("risk_level"),
            "risk_score": line.get("risk_score"),
            "category": line.get("category"),
            "description": line.get("description"),
            "submission_total": line.get("submission_total"),
            "gross_profit": line.get("gross_profit"),
            "margin_pct": line.get("margin_pct"),
            "confidence": line.get("confidence"),
            "win_probability_band": line.get("win_probability_band"),
            "risk_flags": line.get("risk_flags", []),
            "defense_note": note,
            "commercial_assumptions": assumptions,
            "negotiation_priority": guidance["priority"],
            "negotiation_actions": guidance["actions"],
        })

    critical = [x for x in defense_lines if x["risk_level"] == "CRITICAL"]
    high = [x for x in defense_lines if x["risk_level"] == "HIGH"]

    assumption_register = {
        "generated_at": now_iso(),
        "assumptions": [
            {
                "line_no": x["line_no"],
                "description": x["description"],
                "assumptions": x["commercial_assumptions"],
            }
            for x in defense_lines
            if x["commercial_assumptions"]
        ],
    }

    negotiation_register = {
        "generated_at": now_iso(),
        "critical_negotiations": [
            x for x in defense_lines
            if x["negotiation_priority"] == "CRITICAL"
        ],
        "high_negotiations": [
            x for x in defense_lines
            if x["negotiation_priority"] == "HIGH"
        ],
        "medium_negotiations": [
            x for x in defense_lines
            if x["negotiation_priority"] == "MEDIUM"
        ][:500],
    }

    risk_counts = Counter(x["risk_level"] for x in defense_lines)
    category_counts = Counter(x["category"] for x in defense_lines)
    negotiation_counts = Counter(x["negotiation_priority"] for x in defense_lines)

    summary = {
        "generated_at": now_iso(),
        "lines_reviewed": len(defense_lines),
        "critical_lines": len(critical),
        "high_risk_lines": len(high),
        "risk_counts": dict(risk_counts),
        "category_counts": dict(category_counts),
        "negotiation_priority_counts": dict(negotiation_counts),
        "submission_value": submission.get("summary", {}).get("final_submission_value"),
        "projected_profit": submission.get("summary", {}).get("projected_gross_profit"),
        "average_margin_pct": submission.get("summary", {}).get("average_margin_pct"),
    }

    report = {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "critical_defense_lines": critical,
        "high_risk_defense_lines": high[:500],
        "defense_lines": defense_lines,
        "category_risk": category_risk,
    }

    return report, assumption_register, negotiation_register, summary


def write_defense_csv(path, rows):
    fields = [
        "line_no",
        "risk_level",
        "risk_score",
        "category",
        "submission_total",
        "gross_profit",
        "margin_pct",
        "confidence",
        "win_probability_band",
        "negotiation_priority",
        "risk_flags",
        "defense_note",
        "description",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for row in rows:
            r = dict(row)
            r["risk_flags"] = ",".join(r.get("risk_flags") or [])
            writer.writerow({k: r.get(k) for k in fields})


def main():
    report, assumptions, negotiation, summary = build_reports()

    write_json(DEFENSE_JSON, report)
    write_json(ASSUMPTIONS_FILE, assumptions)
    write_json(NEGOTIATION_FILE, negotiation)
    write_json(SUMMARY_FILE, summary)
    write_defense_csv(DEFENSE_CSV, report["defense_lines"])

    print(f"Bid defense report written: {DEFENSE_JSON}")
    print(f"Defense CSV written: {DEFENSE_CSV}")
    print(f"Assumptions written: {ASSUMPTIONS_FILE}")
    print(f"Negotiation guidance written: {NEGOTIATION_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")

    print(f"Lines reviewed: {summary['lines_reviewed']}")
    print(f"Critical lines: {summary['critical_lines']}")
    print(f"High-risk lines: {summary['high_risk_lines']}")

    print("\nNegotiation priorities:")
    for k, v in summary["negotiation_priority_counts"].items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
