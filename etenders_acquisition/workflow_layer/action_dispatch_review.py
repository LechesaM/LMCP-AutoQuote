import json
from pathlib import Path
from datetime import datetime, timezone

ACTION_SUMMARY_PATH = Path("runtime/adjudication/actions/negotiation_action_summary.json")
ACTION_REVIEW_PATH = Path("runtime/adjudication/actions/action_dispatch_review.json")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def load_action_summary():
    if not ACTION_SUMMARY_PATH.exists():
        raise FileNotFoundError(
            f"Action summary not found: {ACTION_SUMMARY_PATH}. "
            "Run negotiation_action_generator first."
        )

    with open(ACTION_SUMMARY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_action_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_action_dispatch_review():
    summary = load_action_summary()
    review_items = []

    for action in summary.get("actions", []):
        action_file = Path(action["action_file"])
        issues = []

        if not action_file.exists():
            issues.append("action_file_missing")
            action_payload = {}
        else:
            action_payload = load_action_file(action_file)

        if not action_payload.get("subject"):
            issues.append("missing_subject")

        if not action_payload.get("body"):
            issues.append("missing_body")

        if not action_payload.get("supplier_name"):
            issues.append("missing_supplier_name")

        if not action_payload.get("rfq_reference"):
            issues.append("missing_rfq_reference")

        dispatch_ready = len(issues) == 0

        review_items.append({
            "supplier_name": action.get("supplier_name"),
            "rfq_reference": action.get("rfq_reference"),
            "decision": action.get("decision"),
            "action_type": action.get("action_type"),
            "action_file": str(action_file),
            "subject": action_payload.get("subject"),
            "body_preview": (action_payload.get("body") or "")[:500],
            "dispatch_ready": dispatch_ready,
            "issues": issues,
            "reviewed_at": utc_now()
        })

    output = {
        "generated_at": utc_now(),
        "total_actions": len(review_items),
        "dispatch_ready_count": sum(1 for item in review_items if item["dispatch_ready"]),
        "blocked_count": sum(1 for item in review_items if not item["dispatch_ready"]),
        "actions": review_items
    }

    ACTION_REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(ACTION_REVIEW_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    return output


def print_review(review):
    print("\nACTION DISPATCH REVIEW")
    print("=" * 80)
    print(f"Total actions: {review['total_actions']}")
    print(f"Ready:         {review['dispatch_ready_count']}")
    print(f"Blocked:       {review['blocked_count']}")
    print("=" * 80)

    for action in review["actions"]:
        status = "READY" if action["dispatch_ready"] else "BLOCKED"

        print(f"\n{status}: {action['supplier_name']}")
        print(f"  RFQ Ref: {action['rfq_reference']}")
        print(f"  Action: {action['action_type']}")
        print(f"  Decision: {action['decision']}")
        print(f"  Subject: {action['subject']}")
        print(f"  File: {action['action_file']}")

        if action["issues"]:
            print(f"  Issues: {', '.join(action['issues'])}")

    print("\nReview file written:")
    print(ACTION_REVIEW_PATH)


if __name__ == "__main__":
    review = build_action_dispatch_review()
    print_review(review)
