import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


RUNTIME_DIR = Path("/Users/cash/Documents/runtime/manual_production")

WORKFLOW_STATE_FILE = RUNTIME_DIR / "workflow_state.jsonl"
WORKFLOW_EVENTS_FILE = RUNTIME_DIR / "workflow_events.jsonl"
QUOTE_PACK_DIR = RUNTIME_DIR / "quote_packs"

MAX_ITEMS = 20


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def safe_name(value):
    value = str(value or "unknown")
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in value)[:80]


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


def create_quote_pack(workflow):
    tender_id = workflow.get("tender_id") or workflow.get("workflow_id")
    title = workflow.get("title") or ""
    department = workflow.get("department") or ""
    province = workflow.get("province") or ""
    closing_date = workflow.get("closing_date") or ""

    pack_id = f"QPACK-{uuid.uuid4().hex[:12]}"
    pack_dir = QUOTE_PACK_DIR / safe_name(tender_id)

    pack_dir.mkdir(parents=True, exist_ok=True)

    quote_summary = {
        "pack_id": pack_id,
        "workflow_id": workflow.get("workflow_id"),
        "tender_id": tender_id,
        "title": title,
        "department": department,
        "province": province,
        "closing_date": closing_date,
        "created_at": utc_now(),
        "quote_ready": True,
        "status": "quote_generated",
        "pricing_basis": "manual_pricing_required",
        "notes": [
            "Initial quote pack generated from evaluated RFQ metadata.",
            "BOQ/document extraction worker still required for final pricing automation.",
            "Manual review required before submission.",
        ],
    }

    quote_letter = f"""
LMCP AutoQuote - Draft Quote Pack

Tender / RFQ: {tender_id}
Department: {department}
Province: {province}
Closing Date: {closing_date}

Title:
{title}

Status:
Quote pack generated for manual review.

Pricing:
Manual pricing required until BOQ extraction worker is connected.

Governance:
This quote pack is not a final submission. Operator review is required.
""".strip()

    manifest_path = pack_dir / "quote_summary.json"
    letter_path = pack_dir / "draft_quote_letter.txt"

    with open(manifest_path, "w") as f:
        json.dump(quote_summary, f, indent=2, ensure_ascii=False)

    with open(letter_path, "w") as f:
        f.write(quote_letter)

    return {
        "pack_id": pack_id,
        "pack_dir": str(pack_dir),
        "manifest_path": str(manifest_path),
        "letter_path": str(letter_path),
    }


def emit_event(workflow, pack_info):
    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:12]}",
        "workflow_id": workflow.get("workflow_id"),
        "tender_id": workflow.get("tender_id"),
        "event_type": "quote_pack_generated",
        "status": "quote_ready",
        "created_at": utc_now(),
        "payload": {
            "pack_id": pack_info["pack_id"],
            "pack_dir": pack_info["pack_dir"],
            "manifest_path": pack_info["manifest_path"],
            "letter_path": pack_info["letter_path"],
        },
    }

    append_jsonl(WORKFLOW_EVENTS_FILE, event)


def main():
    rows = read_jsonl(WORKFLOW_STATE_FILE)
    workflows = latest_workflows(rows)

    candidates = [
        wf for wf in workflows
        if wf.get("stage") == "evaluated"
        and wf.get("status") == "pending_quote_pack"
    ]

    processed = 0

    for wf in candidates[:MAX_ITEMS]:
        pack_info = create_quote_pack(wf)

        new_wf = dict(wf)
        new_wf["previous_stage"] = wf.get("stage")
        new_wf["stage"] = "quote_generated"
        new_wf["status"] = "quote_ready"
        new_wf["quote_ready"] = True
        new_wf["quote_pack"] = pack_info
        new_wf["updated_at"] = utc_now()

        append_jsonl(WORKFLOW_STATE_FILE, new_wf)
        emit_event(new_wf, pack_info)

        processed += 1

    print(f"Quote pack generator complete | generated={processed}")


if __name__ == "__main__":
    main()
