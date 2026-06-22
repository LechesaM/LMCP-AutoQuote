import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


RUNTIME_DIR = Path("/Users/cash/Documents/runtime/manual_production")

WORKFLOW_STATE_FILE = RUNTIME_DIR / "workflow_state.jsonl"
WORKFLOW_EVENTS_FILE = RUNTIME_DIR / "workflow_events.jsonl"

MAX_ITEMS = 50


ELIGIBLE_KEYWORDS = [
    "supply",
    "delivery",
    "construction",
    "repairs",
    "maintenance",
    "installation",
    "building",
    "renovation",
    "civil",
    "electrical",
    "plumbing",
    "security",
    "fencing",
    "road",
    "paving",
    "stormwater",
    "boq",
    "bill of quantities",
]

REFUSE_KEYWORDS = [
    "catering",
    "decor",
    "website",
    "consultant",
    "consulting",
    "audit",
    "financial model",
    "expected credit loss",
    "training",
    "event",
    "awards",
    "legal",
]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path):
    rows = []

    if not path.exists():
        return rows

    with open(path, "r") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            try:
                rows.append(json.loads(line))
            except Exception:
                continue

    return rows


def append_jsonl(path, payload):
    with open(path, "a") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def latest_workflows(rows):
    latest = {}

    for row in rows:
        workflow_id = row.get("workflow_id")

        if not workflow_id:
            continue

        latest[workflow_id] = row

    return list(latest.values())


def classify(workflow):
    text = " ".join([
        str(workflow.get("title", "")),
        str(workflow.get("department", "")),
        str(workflow.get("province", "")),
    ]).lower()

    for kw in REFUSE_KEYWORDS:
        if kw in text:
            return "refused", f"Matched refusal keyword: {kw}"

    for kw in ELIGIBLE_KEYWORDS:
        if kw in text:
            return "evaluated", f"Matched eligible keyword: {kw}"

    return "review_ready", "No strong auto-classification match; requires manual review"


def emit_event(workflow, event_type, status, reason):
    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:12]}",
        "workflow_id": workflow.get("workflow_id"),
        "tender_id": workflow.get("tender_id"),
        "event_type": event_type,
        "status": status,
        "created_at": utc_now(),
        "payload": {
            "title": workflow.get("title"),
            "department": workflow.get("department"),
            "province": workflow.get("province"),
            "closing_date": workflow.get("closing_date"),
            "reason": reason,
        },
    }

    append_jsonl(WORKFLOW_EVENTS_FILE, event)


def main():
    rows = read_jsonl(WORKFLOW_STATE_FILE)
    workflows = latest_workflows(rows)

    queued = [
        wf for wf in workflows
        if wf.get("stage") == "review_queue"
        and wf.get("status") == "queued"
    ]

    processed = 0
    evaluated = 0
    refused = 0
    manual_review = 0

    for wf in queued[:MAX_ITEMS]:
        new_stage, reason = classify(wf)

        new_wf = dict(wf)
        new_wf["previous_stage"] = wf.get("stage")
        new_wf["stage"] = new_stage
        new_wf["status"] = (
            "refused" if new_stage == "refused"
            else "pending_quote_pack" if new_stage == "evaluated"
            else "manual_review_required"
        )
        new_wf["quote_ready"] = False
        new_wf["classification_reason"] = reason
        new_wf["updated_at"] = utc_now()

        append_jsonl(WORKFLOW_STATE_FILE, new_wf)

        emit_event(
            new_wf,
            event_type="rfq_classified",
            status=new_wf["status"],
            reason=reason,
        )

        processed += 1

        if new_stage == "evaluated":
            evaluated += 1
        elif new_stage == "refused":
            refused += 1
        else:
            manual_review += 1

    print(
        f"Quote worker complete | "
        f"queued_before={len(queued)} "
        f"processed={processed} "
        f"evaluated={evaluated} "
        f"refused={refused} "
        f"manual_review={manual_review}"
    )


if __name__ == "__main__":
    main()
