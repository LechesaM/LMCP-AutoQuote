import json
import uuid
from datetime import datetime, timezone

import psycopg

PG_CONN = (
    "host=localhost "
    "port=5432 "
    "dbname=etenders "
    "user=etenders "
    "password=etenders"
)

WORKFLOW_EVENTS_FILE = (
    "/Users/cash/Documents/runtime/manual_production/workflow_events.jsonl"
)

WORKFLOW_STATE_FILE = (
    "/Users/cash/Documents/runtime/manual_production/workflow_state.jsonl"
)

HARVEST_FILE = (
    "/Users/cash/Documents/runtime/manual_production/harvest_opportunities.jsonl"
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def append_jsonl(path, payload):
    with open(path, "a") as f:
        f.write(json.dumps(payload) + "\n")


def load_existing_ids():
    ids = set()

    try:
        with open(WORKFLOW_STATE_FILE, "r") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    tender_id = obj.get("tender_id")
                    if tender_id:
                        ids.add(tender_id)
                except:
                    pass
    except FileNotFoundError:
        pass

    return ids


def fetch_tenders(limit=200):
    conn = psycopg.connect(PG_CONN)

    cur = conn.cursor()

    cur.execute("""
        SELECT
            tender_id,
            title,
            department,
            province,
            closing_date
        FROM tenders
        LIMIT %s
    """, (limit,))

    rows = cur.fetchall()

    conn.close()

    return rows


def main():

    existing = load_existing_ids()

    rows = fetch_tenders()

    seeded = 0

    for row in rows:

        tender_id, title, department, province, closing_date = row

        if not tender_id:
            continue

        if tender_id in existing:
            continue

        workflow_id = f"wf-{uuid.uuid4().hex[:12]}"
        event_id = f"evt-{uuid.uuid4().hex[:12]}"

        workflow_state = {
            "workflow_id": workflow_id,
            "tender_id": tender_id,
            "title": title,
            "department": department,
            "province": province,
            "closing_date": closing_date,
            "stage": "review_queue",
            "status": "queued",
            "quote_ready": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        workflow_event = {
            "event_id": event_id,
            "workflow_id": workflow_id,
            "tender_id": tender_id,
            "event_type": "rfq_harvested",
            "status": "queued",
            "created_at": utc_now(),
            "payload": {
                "title": title,
                "department": department,
                "province": province,
                "closing_date": closing_date,
            }
        }

        harvest_record = {
            "tender_id": tender_id,
            "title": title,
            "department": department,
            "province": province,
            "closing_date": closing_date,
            "harvested_at": utc_now(),
            "source": "postgres_seed"
        }

        append_jsonl(WORKFLOW_STATE_FILE, workflow_state)
        append_jsonl(WORKFLOW_EVENTS_FILE, workflow_event)
        append_jsonl(HARVEST_FILE, harvest_record)

        seeded += 1

    print(f"Seeded {seeded} runtime workflow items")


if __name__ == "__main__":
    main()
