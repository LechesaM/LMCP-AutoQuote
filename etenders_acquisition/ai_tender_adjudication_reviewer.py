#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

SUBMISSION_FILE = (
    RUNTIME_DIR
    / "submission_pack"
    / "final_submission_pricing_schedule.json"
)

DEFENSE_FILE = (
    RUNTIME_DIR
    / "bid_defense"
    / "intelligent_bid_defense_report.json"
)

HEATMAP_FILE = (
    RUNTIME_DIR
    / "commercial_risk_heatmap"
    / "commercial_risk_heatmap.json"
)

OUT_DIR = RUNTIME_DIR / "ai_tender_adjudication"

REVIEW_FILE = OUT_DIR / "ai_tender_adjudication_review.json"
SUMMARY_FILE = OUT_DIR / "ai_tender_adjudication_summary.json"
CLARIFICATIONS_FILE = OUT_DIR / "likely_client_clarifications.json"


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


def score_band(score):
    if score >= 85:
        return "PASS"
    if score >= 70:
        return "PASS_WITH_REVIEW"
    if score >= 55:
        return "CONDITIONAL_REVIEW"
    return "HIGH_RISK_REVIEW"


def clarification_for(line):
    desc = line.get("description")
    risk_flags = line.get("risk_flags", [])
    confidence = line.get("confidence")
    total = money(line.get("submission_total"))

    questions = []

    if confidence in ["FALLBACK_LOW", "LOW"]:
        questions.append("Please confirm the basis of rate and supplier quotation support.")

    if "major_value_exposure" in risk_flags or total > 1000000:
        questions.append("Please provide commercial justification for this high-value line.")

    if "technical_specialist" in risk_flags:
        questions.append("Please confirm specification compliance and OEM/supplier confirmation.")

    if "thin_margin" in risk_flags:
        questions.append("Please confirm sustainability of the rate and inclusion of all costs.")

    if not questions:
        questions.append("No specific clarification expected.")

    return {
        "line_no": line.get("line_no"),
        "description": desc,
        "submission_total": total,
        "questions": questions,
    }


def review_line(line):
    score = 100
    issues = []

    risk_level = line.get("risk_level")
    confidence = line.get("confidence")
    margin = money(line.get("margin_pct"))
    total = money(line.get("submission_total"))
    action = line.get("recommended_action")

    if risk_level == "CRITICAL":
        score -= 35
        issues.append("critical_commercial_risk")

    elif risk_level == "HIGH":
        score -= 20
        issues.append("high_commercial_risk")

    if confidence in ["FALLBACK_LOW", "LOW"]:
        score -= 15
        issues.append("weak_pricing_confidence")

    if margin < 8:
        score -= 15
        issues.append("margin_below_minimum_threshold")

    if total > 1000000:
        score -= 10
        issues.append("major_value_exposure")

    if action == "REVIEW_PRICE":
        score -= 10
        issues.append("requires_price_review")

    if action == "DO_NOT_SUBMIT":
        score -= 50
        issues.append("do_not_submit_flag")

    score = max(0, min(100, score))

    return {
        "line_no": line.get("line_no"),
        "description": line.get("description"),
        "category": line.get("category"),
        "submission_total": total,
        "margin_pct": margin,
        "confidence": confidence,
        "risk_level": risk_level,
        "recommended_action": action,
        "adjudication_score": score,
        "adjudication_band": score_band(score),
        "issues": issues,
    }


def main():
    submission = load_json(SUBMISSION_FILE, default={})
    defense = load_json(DEFENSE_FILE, default={})
    heatmap = load_json(HEATMAP_FILE, default={})

    lines = defense.get("defense_lines", [])
    heat_lines = heatmap.get("all_lines", [])

    reviewed = [review_line(line) for line in lines]

    total_value = money(sum(x["submission_total"] for x in reviewed))
    weighted_score = 0

    for line in reviewed:
        value = money(line.get("submission_total"))
        weighted_score += line["adjudication_score"] * value

    commercial_compliance_score = round(
        weighted_score / total_value,
        2
    ) if total_value else 0

    issue_counter = Counter()
    band_counter = Counter(x["adjudication_band"] for x in reviewed)
    category_counter = Counter(x["category"] or "unknown" for x in reviewed)

    for line in reviewed:
        for issue in line["issues"]:
            issue_counter[issue] += 1

    critical_lines = [
        x for x in reviewed
        if x["adjudication_band"] in ["HIGH_RISK_REVIEW", "CONDITIONAL_REVIEW"]
    ]

    clarification_lines = [
        clarification_for(x)
        for x in lines
        if x.get("risk_level") in ["CRITICAL", "HIGH"]
    ]

    if commercial_compliance_score >= 80 and not any(
        x["risk_level"] == "CRITICAL" for x in lines
    ):
        recommendation = "APPROVE_FOR_SUBMISSION"

    elif commercial_compliance_score >= 70:
        recommendation = "APPROVE_AFTER_COMMERCIAL_REVIEW"

    elif commercial_compliance_score >= 60:
        recommendation = "HOLD_FOR_RATE_VALIDATION"

    else:
        recommendation = "DO_NOT_SUBMIT_WITHOUT_REWORK"

    financial_sustainability_score = max(
        0,
        min(
            100,
            round(
                100
                - issue_counter.get("margin_below_minimum_threshold", 0) * 0.5
                - issue_counter.get("major_value_exposure", 0) * 2
                - issue_counter.get("weak_pricing_confidence", 0) * 0.08,
                2,
            ),
        ),
    )

    disqualification_risk_score = max(
        0,
        min(
            100,
            round(
                issue_counter.get("do_not_submit_flag", 0) * 25
                + issue_counter.get("critical_commercial_risk", 0) * 6
                + issue_counter.get("weak_pricing_confidence", 0) * 0.05,
                2,
            ),
        ),
    )

    summary = {
        "generated_at": now_iso(),
        "lines_reviewed": len(reviewed),
        "submission_value": submission.get("summary", {}).get("final_submission_value"),
        "projected_profit": submission.get("summary", {}).get("projected_gross_profit"),
        "average_margin_pct": submission.get("summary", {}).get("average_margin_pct"),
        "commercial_compliance_score": commercial_compliance_score,
        "financial_sustainability_score": financial_sustainability_score,
        "disqualification_risk_score": disqualification_risk_score,
        "executive_recommendation": recommendation,
        "adjudication_band_counts": dict(band_counter),
        "issue_counts": dict(issue_counter),
        "category_counts": dict(category_counter),
        "likely_clarification_count": len(clarification_lines),
    }

    review = {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "reviewed_lines": reviewed,
        "priority_review_lines": sorted(
            critical_lines,
            key=lambda x: x["adjudication_score"]
        )[:500],
    }

    clarifications = {
        "generated_at": summary["generated_at"],
        "clarifications": clarification_lines,
    }

    write_json(REVIEW_FILE, review)
    write_json(SUMMARY_FILE, summary)
    write_json(CLARIFICATIONS_FILE, clarifications)

    print(f"AI adjudication review written: {REVIEW_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Clarifications written: {CLARIFICATIONS_FILE}")
    print(f"Executive recommendation: {summary['executive_recommendation']}")
    print(f"Commercial compliance score: {summary['commercial_compliance_score']}")
    print(f"Financial sustainability score: {summary['financial_sustainability_score']}")
    print(f"Disqualification risk score: {summary['disqualification_risk_score']}")


if __name__ == "__main__":
    main()
