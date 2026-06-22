import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

from workflow_layer.email_dispatcher import send_email

ACTION_REVIEW_PATH = Path("runtime/adjudication/actions/action_dispatch_review.json")
ACTION_SEND_LOG_PATH = Path("runtime/adjudication/actions/action_send_log.json")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def load_action_review():
    if not ACTION_REVIEW_PATH.exists():
        raise FileNotFoundError(
            f"Action review not found: {ACTION_REVIEW_PATH}. "
            "Run action_dispatch_review first."
        )

    with open(ACTION_REVIEW_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_action_payload(action_file):
    with open(action_file, "r", encoding="utf-8") as f:
        return json.load(f)


def write_send_log(items):
    ACTION_SEND_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": utc_now(),
        "total_attempted": len(items),
        "sent_count": sum(1 for i in items if i["send_status"] == "sent"),
        "blocked_count": sum(1 for i in items if i["send_status"] == "blocked"),
        "failed_count": sum(1 for i in items if i["send_status"] == "failed"),
        "actions": items
    }

    with open(ACTION_SEND_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return payload


def send_reviewed_actions(send_live=False):
    review = load_action_review()
    send_log = []

    for action in review.get("actions", []):
        supplier_name = action.get("supplier_name")
        rfq_reference = action.get("rfq_reference")
        action_type = action.get("action_type")
        action_file = action.get("action_file")

        if not action.get("dispatch_ready"):
            send_log.append({
                "supplier_name": supplier_name,
                "rfq_reference": rfq_reference,
                "action_type": action_type,
                "send_status": "blocked",
                "reason": "dispatch_ready_false",
                "issues": action.get("issues", []),
                "processed_at": utc_now()
            })
            continue

        payload = load_action_payload(action_file)

        supplier_email = None

        commercial_data = payload.get("commercial_data", {})
        supplier_email = commercial_data.get("email")

        if not supplier_email:
            # Fallback: route back to same dummy supplier contact emails used in Phase 2A
            if supplier_name == "Bearing Man Group":
                supplier_email = "sales@bmgworld.net"
            elif supplier_name == "Builders Warehouse":
                supplier_email = "quotes@builders.co.za"

        if not supplier_email:
            send_log.append({
                "supplier_name": supplier_name,
                "rfq_reference": rfq_reference,
                "action_type": action_type,
                "send_status": "blocked",
                "reason": "missing_supplier_email",
                "processed_at": utc_now()
            })
            continue

        if not send_live:
            send_log.append({
                "supplier_name": supplier_name,
                "rfq_reference": rfq_reference,
                "action_type": action_type,
                "email": supplier_email,
                "subject": payload.get("subject"),
                "send_status": "blocked",
                "reason": "dry_run_only_missing_send_live_flag",
                "processed_at": utc_now()
            })
            continue

        try:
            send_email(
                to_email=supplier_email,
                subject=payload["subject"],
                body=payload["body"],
                attachment_paths=[]
            )

            send_log.append({
                "supplier_name": supplier_name,
                "rfq_reference": rfq_reference,
                "action_type": action_type,
                "email": supplier_email,
                "subject": payload.get("subject"),
                "send_status": "sent",
                "processed_at": utc_now()
            })

            print(f"SENT ACTION: {supplier_name} | {action_type}")

        except Exception as exc:
            send_log.append({
                "supplier_name": supplier_name,
                "rfq_reference": rfq_reference,
                "action_type": action_type,
                "email": supplier_email,
                "subject": payload.get("subject"),
                "send_status": "failed",
                "error": str(exc),
                "processed_at": utc_now()
            })

            print(f"FAILED ACTION: {supplier_name} | {action_type} | {exc}")

    log = write_send_log(send_log)

    print("\nACTION SEND RESULT")
    print("=" * 80)
    print(f"Attempted: {log['total_attempted']}")
    print(f"Sent:      {log['sent_count']}")
    print(f"Blocked:   {log['blocked_count']}")
    print(f"Failed:    {log['failed_count']}")
    print(f"Log:       {ACTION_SEND_LOG_PATH}")

    return log


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--send-live",
        action="store_true",
        help="Actually send action emails. Without this flag, dry-run only."
    )

    args = parser.parse_args()

    send_reviewed_actions(send_live=args.send_live)
