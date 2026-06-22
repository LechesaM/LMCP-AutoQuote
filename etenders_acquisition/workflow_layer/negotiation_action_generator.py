import json
from pathlib import Path
from datetime import datetime, timezone

ADJUDICATION_PATH = Path("runtime/adjudication/live_adjudication_summary.json")
ACTION_OUTPUT_DIR = Path("runtime/adjudication/actions")
ACTION_SUMMARY_PATH = ACTION_OUTPUT_DIR / "negotiation_action_summary.json"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def load_adjudication():
    if not ADJUDICATION_PATH.exists():
        raise FileNotFoundError(
            f"Adjudication summary not found: {ADJUDICATION_PATH}. "
            "Run live_adjudication_engine first."
        )

    with open(ADJUDICATION_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_award_action(decision):
    subject = (
        f"Recommended Award | {decision['supplier_name']} | "
        f"{decision['rfq_reference']}"
    )

    body = f"""
Dear {decision['supplier_name']},

Following commercial adjudication of your quotation, your submission is recommended for award subject to final executive approval.

RFQ Reference:
{decision['rfq_reference']}

Target Value:
R{decision['target_total']:,.2f}

Quoted Value:
R{decision['quoted_total']:,.2f}

Variance:
R{decision['variance']:,.2f} ({decision['variance_pct']:.2f}%)

Commercial Decision:
{decision['decision']}

Please confirm:

- Final price validity
- Stock availability
- Delivery lead time
- VAT status
- Any commercial exclusions
- Earliest delivery date

Regards,

LMCP AutoQuote Procurement
""".strip()

    return {
        "action_type": "AWARD_CONFIRMATION",
        "subject": subject,
        "body": body
    }


def build_negotiation_action(decision):
    requested_improvement_pct = 2.0
    requested_value = decision["quoted_total"] * (1 - requested_improvement_pct / 100)

    subject = (
        f"Negotiation Request | {decision['supplier_name']} | "
        f"{decision['rfq_reference']}"
    )

    body = f"""
Dear {decision['supplier_name']},

Thank you for your quotation.

Following commercial adjudication, your quotation is commercially acceptable but requires further improvement before award recommendation.

RFQ Reference:
{decision['rfq_reference']}

Current Quoted Value:
R{decision['quoted_total']:,.2f}

Target Procurement Value:
R{decision['target_total']:,.2f}

Current Variance:
R{decision['variance']:,.2f} ({decision['variance_pct']:.2f}%)

Requested Commercial Improvement:
2.00%

Requested Revised Value:
R{requested_value:,.2f}

Please confirm whether you can improve your offer and resubmit your best and final quotation.

Please also confirm:

- Final unit rates
- Delivery lead time
- Stock availability
- VAT status
- Commercial exclusions
- Price validity period

Regards,

LMCP AutoQuote Procurement
""".strip()

    return {
        "action_type": "NEGOTIATION_REQUEST",
        "subject": subject,
        "body": body,
        "requested_improvement_pct": requested_improvement_pct,
        "requested_value": round(requested_value, 2)
    }


def build_review_action(decision):
    subject = (
        f"Hold for Review | {decision['supplier_name']} | "
        f"{decision['rfq_reference']}"
    )

    body = f"""
Supplier requires executive review before any award or negotiation action.

Supplier:
{decision['supplier_name']}

RFQ Reference:
{decision['rfq_reference']}

Quoted Value:
R{decision['quoted_total']:,.2f}

Target Value:
R{decision['target_total']:,.2f}

Variance:
R{decision['variance_pct']:.2f}%

Reason:
{decision['reason']}
""".strip()

    return {
        "action_type": "EXECUTIVE_REVIEW",
        "subject": subject,
        "body": body
    }


def generate_actions():
    adjudication = load_adjudication()
    ACTION_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    actions = []

    for decision in adjudication.get("decisions", []):
        if decision["decision"] == "RECOMMEND_AWARD":
            action = build_award_action(decision)
        elif decision["decision"] == "RECOMMEND_NEGOTIATE":
            action = build_negotiation_action(decision)
        else:
            action = build_review_action(decision)

        safe_supplier = (
            decision["supplier_name"]
            .upper()
            .replace(" ", "_")
            .replace("/", "_")
        )

        action_file = ACTION_OUTPUT_DIR / (
            f"{decision['rfq_reference']}_{action['action_type']}.json"
        )

        payload = {
            "generated_at": utc_now(),
            "supplier_name": decision["supplier_name"],
            "rfq_reference": decision["rfq_reference"],
            "decision": decision["decision"],
            "action_type": action["action_type"],
            "subject": action["subject"],
            "body": action["body"],
            "decision_reason": decision["reason"],
            "commercial_data": decision
        }

        if "requested_improvement_pct" in action:
            payload["requested_improvement_pct"] = action["requested_improvement_pct"]
            payload["requested_value"] = action["requested_value"]

        with open(action_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        actions.append({
            "supplier_name": decision["supplier_name"],
            "rfq_reference": decision["rfq_reference"],
            "decision": decision["decision"],
            "action_type": action["action_type"],
            "action_file": str(action_file)
        })

        print(
            f"ACTION GENERATED: {decision['supplier_name']} | "
            f"{action['action_type']}"
        )

    summary = {
        "generated_at": utc_now(),
        "total_actions": len(actions),
        "award_confirmations": sum(
            1 for a in actions if a["action_type"] == "AWARD_CONFIRMATION"
        ),
        "negotiation_requests": sum(
            1 for a in actions if a["action_type"] == "NEGOTIATION_REQUEST"
        ),
        "executive_reviews": sum(
            1 for a in actions if a["action_type"] == "EXECUTIVE_REVIEW"
        ),
        "actions": actions
    }

    with open(ACTION_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Negotiation action summary written: {ACTION_SUMMARY_PATH}")
    return summary


if __name__ == "__main__":
    generate_actions()
