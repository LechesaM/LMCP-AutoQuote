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

WIN_FILE = (
    RUNTIME_DIR
    / "commercial_intelligence"
    / "bid_win_probability_analysis.json"
)

ADJUDICATION_FILE = (
    RUNTIME_DIR
    / "ai_tender_adjudication"
    / "ai_tender_adjudication_review.json"
)

NEGOTIATION_FILE = (
    RUNTIME_DIR
    / "procurement_negotiation_intelligence"
    / "best_and_final_offer_simulation.json"
)

OUT_DIR = RUNTIME_DIR / "award_prediction"

PREDICTION_FILE = OUT_DIR / "tender_award_prediction.json"
SUMMARY_FILE = OUT_DIR / "tender_award_prediction_summary.json"


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


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def probability_band(score):
    if score >= 80:
        return "VERY_HIGH"
    if score >= 65:
        return "HIGH"
    if score >= 50:
        return "MEDIUM"
    if score >= 35:
        return "LOW"
    return "VERY_LOW"


def award_recommendation(score, adjudication_reco):
    if adjudication_reco == "DO_NOT_SUBMIT_WITHOUT_REWORK":
        if score >= 60:
            return "NEGOTIATE_AND_REWORK_BEFORE_SUBMISSION"
        return "DO_NOT_SUBMIT_YET"

    if score >= 70:
        return "SUBMIT"
    if score >= 55:
        return "SUBMIT_AFTER_TARGETED_REVIEW"
    return "REWORK_OR_SKIP"


def estimate_award_score(submission, win, adjudication, negotiation):
    score = 50
    drivers = []

    avg_win = win.get("summary", {}).get("average_win_probability_score", 0)
    compliance = adjudication.get("summary", {}).get("commercial_compliance_score", 0)
    sustainability = adjudication.get("summary", {}).get("financial_sustainability_score", 0)
    disq_risk = adjudication.get("summary", {}).get("disqualification_risk_score", 0)

    if avg_win:
        score += (avg_win - 50) * 0.35
        drivers.append(f"win_score:{avg_win}")

    if compliance:
        score += (compliance - 60) * 0.25
        drivers.append(f"commercial_compliance:{compliance}")

    if sustainability:
        score += (sustainability - 50) * 0.20
        drivers.append(f"financial_sustainability:{sustainability}")

    if disq_risk:
        score -= disq_risk * 0.25
        drivers.append(f"disqualification_risk:{disq_risk}")

    current_bid = money(submission.get("summary", {}).get("final_submission_value"))
    bafo = negotiation.get("bafo_scenarios", {})

    recommended_bafo = money(
        bafo.get("recommended", {}).get("bafo_value")
    )

    if current_bid and recommended_bafo:
        reduction_pct = ((current_bid - recommended_bafo) / current_bid) * 100

        if reduction_pct >= 10:
            score += 10
            drivers.append(f"bafo_reduction_opportunity:{round(reduction_pct,2)}%")

        elif reduction_pct >= 5:
            score += 5
            drivers.append(f"moderate_bafo_opportunity:{round(reduction_pct,2)}%")

    critical_lines = adjudication.get("summary", {}).get("adjudication_band_counts", {}).get(
        "HIGH_RISK_REVIEW",
        0,
    )

    if critical_lines > 0:
        score -= min(20, critical_lines * 2)
        drivers.append(f"critical_review_lines:{critical_lines}")

    return clamp(round(score, 2)), drivers


def build_scenario(name, base_bid, scenario_bid, base_score):
    if not base_bid or not scenario_bid:
        delta_pct = 0
    else:
        delta_pct = ((base_bid - scenario_bid) / base_bid) * 100

    score = base_score

    if delta_pct >= 15:
        score += 15
    elif delta_pct >= 10:
        score += 10
    elif delta_pct >= 5:
        score += 5

    score = clamp(round(score, 2))

    return {
        "scenario": name,
        "bid_value": scenario_bid,
        "bid_reduction_pct": round(delta_pct, 2),
        "award_probability_score": score,
        "award_probability_band": probability_band(score),
    }


def main():
    submission = load_json(SUBMISSION_FILE, default={})
    win = load_json(WIN_FILE, default={})
    adjudication = load_json(ADJUDICATION_FILE, default={})
    negotiation = load_json(NEGOTIATION_FILE, default={})

    base_score, drivers = estimate_award_score(
        submission,
        win,
        adjudication,
        negotiation,
    )

    current_bid = money(submission.get("summary", {}).get("final_submission_value"))

    bafo_scenarios = negotiation.get("bafo_scenarios", {})

    scenarios = [
        build_scenario(
            "current_submission",
            current_bid,
            current_bid,
            base_score,
        )
    ]

    for name, payload in bafo_scenarios.items():
        scenarios.append(
            build_scenario(
                f"bafo_{name}",
                current_bid,
                money(payload.get("bafo_value")),
                base_score,
            )
        )

    best = sorted(
        scenarios,
        key=lambda x: x["award_probability_score"],
        reverse=True,
    )[0]

    adjudication_reco = adjudication.get("summary", {}).get(
        "executive_recommendation"
    )

    recommendation = award_recommendation(
        best["award_probability_score"],
        adjudication_reco,
    )

    band_counts = Counter(x["award_probability_band"] for x in scenarios)

    summary = {
        "generated_at": now_iso(),
        "base_award_probability_score": base_score,
        "base_award_probability_band": probability_band(base_score),
        "best_scenario": best,
        "executive_recommendation": recommendation,
        "current_bid_value": current_bid,
        "adjudication_recommendation": adjudication_reco,
        "score_drivers": drivers,
        "scenario_band_counts": dict(band_counts),
    }

    output = {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "award_scenarios": scenarios,
    }

    write_json(PREDICTION_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"Award prediction written: {PREDICTION_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Base award score: {summary['base_award_probability_score']}")
    print(f"Best scenario: {best['scenario']}")
    print(f"Best scenario score: {best['award_probability_score']}")
    print(f"Executive recommendation: {recommendation}")


if __name__ == "__main__":
    main()
