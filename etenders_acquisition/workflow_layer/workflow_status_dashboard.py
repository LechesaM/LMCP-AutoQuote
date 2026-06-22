import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("runtime/workflow/workflow_layer.db")

RFQ_SUMMARY_PATH = Path("runtime/rfqs/rfq_orchestration_summary.json")
DISPATCH_REVIEW_PATH = Path("runtime/rfqs/rfq_dispatch_review.json")
DISPATCH_LOG_PATH = Path("runtime/rfqs/rfq_dispatch_log.json")

RESPONSE_LOG_PATH = Path("runtime/supplier_responses/response_listener_log.json")
QUOTE_INGESTION_PATH = Path("runtime/supplier_responses/quote_ingestion_summary.json")

ADJUDICATION_PATH = Path("runtime/adjudication/live_adjudication_summary.json")
ACTION_REVIEW_PATH = Path("runtime/adjudication/actions/action_dispatch_review.json")
ACTION_SEND_LOG_PATH = Path("runtime/adjudication/actions/action_send_log.json")

DASHBOARD_OUTPUT_PATH = Path("runtime/workflow/workflow_status_dashboard.json")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def load_json(path, default):
    if not path.exists():
        return default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_db_counts():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    counts = {}

    for table in [
        "supplier_contacts",
        "rfq_batches",
        "supplier_responses",
        "adjudication_decisions"
    ]:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cur.fetchone()[0]
        except Exception:
            counts[table] = 0

    conn.close()
    return counts


def build_dashboard():
    rfq_summary = load_json(RFQ_SUMMARY_PATH, [])
    dispatch_review = load_json(DISPATCH_REVIEW_PATH, {})
    dispatch_log = load_json(DISPATCH_LOG_PATH, {})
    response_log = load_json(RESPONSE_LOG_PATH, {})
    quote_ingestion = load_json(QUOTE_INGESTION_PATH, {})
    adjudication = load_json(ADJUDICATION_PATH, {})
    action_review = load_json(ACTION_REVIEW_PATH, {})
    action_send_log = load_json(ACTION_SEND_LOG_PATH, {})

    quotes = quote_ingestion.get("quotes", [])
    decisions = adjudication.get("decisions", [])

    total_target_value = sum(float(q.get("target_total") or 0) for q in quotes)
    total_quoted_value = sum(float(q.get("quoted_total") or 0) for q in quotes)
    total_variance = total_quoted_value - total_target_value

    total_variance_pct = 0.0
    if total_target_value:
        total_variance_pct = (total_variance / total_target_value) * 100

    dashboard = {
        "generated_at": utc_now(),
        "database_counts": get_db_counts(),
        "rfq_status": {
            "rfqs_created": len(rfq_summary),
            "dispatch_ready": dispatch_review.get("dispatch_ready_count", 0),
            "dispatch_blocked": dispatch_review.get("blocked_count", 0),
            "rfqs_sent": dispatch_log.get("sent_count", 0),
            "rfqs_blocked_dry_run": dispatch_log.get("blocked_count", 0),
            "rfqs_failed": dispatch_log.get("failed_count", 0)
        },
        "response_status": {
            "mailbox_messages_checked": response_log.get("messages_checked", 0),
            "matched_supplier_responses": response_log.get("matched_responses", 0),
            "unmatched_messages": response_log.get("unmatched_messages", 0),
            "quotes_ingested": quote_ingestion.get("total_quotes_ingested", 0)
        },
        "commercial_position": {
            "total_target_value": round(total_target_value, 2),
            "total_quoted_value": round(total_quoted_value, 2),
            "total_variance": round(total_variance, 2),
            "total_variance_pct": round(total_variance_pct, 2)
        },
        "adjudication_status": {
            "total_decisions": adjudication.get("total_decisions", 0),
            "recommended_awards": adjudication.get("recommended_awards", 0),
            "recommended_negotiations": adjudication.get("recommended_negotiations", 0),
            "held_for_review": adjudication.get("held_for_review", 0)
        },
        "action_status": {
            "actions_ready": action_review.get("dispatch_ready_count", 0),
            "actions_blocked": action_review.get("blocked_count", 0),
            "actions_sent": action_send_log.get("sent_count", 0),
            "actions_blocked_dry_run": action_send_log.get("blocked_count", 0),
            "actions_failed": action_send_log.get("failed_count", 0)
        },
        "supplier_decisions": decisions
    }

    DASHBOARD_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(DASHBOARD_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, indent=2)

    return dashboard


def print_dashboard(dashboard):
    cp = dashboard["commercial_position"]

    print("\nLMCP AUTOQUOTE — WORKFLOW STATUS DASHBOARD")
    print("=" * 90)

    print("\nRFQ STATUS")
    print("-" * 90)
    print(f"RFQs created:          {dashboard['rfq_status']['rfqs_created']}")
    print(f"Dispatch ready:        {dashboard['rfq_status']['dispatch_ready']}")
    print(f"RFQs sent:             {dashboard['rfq_status']['rfqs_sent']}")
    print(f"RFQs dry-run blocked:  {dashboard['rfq_status']['rfqs_blocked_dry_run']}")

    print("\nSUPPLIER RESPONSE STATUS")
    print("-" * 90)
    print(f"Mailbox checked:       {dashboard['response_status']['mailbox_messages_checked']}")
    print(f"Matched responses:     {dashboard['response_status']['matched_supplier_responses']}")
    print(f"Quotes ingested:       {dashboard['response_status']['quotes_ingested']}")

    print("\nCOMMERCIAL POSITION")
    print("-" * 90)
    print(f"Target value:          R{cp['total_target_value']:,.2f}")
    print(f"Quoted value:          R{cp['total_quoted_value']:,.2f}")
    print(f"Variance:              R{cp['total_variance']:,.2f}")
    print(f"Variance pct:          {cp['total_variance_pct']:.2f}%")

    print("\nADJUDICATION")
    print("-" * 90)
    print(f"Total decisions:       {dashboard['adjudication_status']['total_decisions']}")
    print(f"Recommended awards:    {dashboard['adjudication_status']['recommended_awards']}")
    print(f"Negotiations:          {dashboard['adjudication_status']['recommended_negotiations']}")
    print(f"Held for review:       {dashboard['adjudication_status']['held_for_review']}")

    print("\nACTIONS")
    print("-" * 90)
    print(f"Actions ready:         {dashboard['action_status']['actions_ready']}")
    print(f"Actions sent:          {dashboard['action_status']['actions_sent']}")
    print(f"Actions dry-run block: {dashboard['action_status']['actions_blocked_dry_run']}")

    print("\nSUPPLIER DECISIONS")
    print("-" * 90)

    for decision in dashboard.get("supplier_decisions", []):
        print(
            f"{decision['supplier_name']} | "
            f"{decision['decision']} | "
            f"Score {decision['final_score']} | "
            f"Quoted R{decision['quoted_total']:,.2f}"
        )

    print("\nDashboard JSON written:")
    print(DASHBOARD_OUTPUT_PATH)


if __name__ == "__main__":
    dashboard = build_dashboard()
    print_dashboard(dashboard)
