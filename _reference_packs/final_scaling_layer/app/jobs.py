"""Scheduled jobs (called by EventBridge -> ECS RunTask)

Commands:
  python -m app.jobs poll_etenders
  python -m app.jobs export_audit_snapshots
  python -m app.jobs create_next_partitions
"""

import sys
from datetime import datetime, timezone

def poll_etenders():
    # TODO: fetch eTenders feed, dedupe, enqueue extract tasks
    print("poll_etenders ok", datetime.now(timezone.utc).isoformat())

def export_audit_snapshots():
    # TODO:
    # - Export send_events/opportunities to S3 in JSONL or Parquet
    # - Partition by date=YYYY-MM-DD
    print("export_audit_snapshots ok", datetime.now(timezone.utc).isoformat())

def create_next_partitions():
    # TODO:
    # - Create next month's partitions for high-volume tables
    print("create_next_partitions ok", datetime.now(timezone.utc).isoformat())

def main():
    if len(sys.argv) < 2:
        print("Missing command")
        raise SystemExit(2)
    cmd = sys.argv[1]
    if cmd == "poll_etenders":
        poll_etenders()
    elif cmd == "export_audit_snapshots":
        export_audit_snapshots()
    elif cmd == "create_next_partitions":
        create_next_partitions()
    else:
        print("Unknown command:", cmd)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
