import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ..workflow_layer.workflow_status_dashboard import build_dashboard
from ..workflow_layer.rfq_dispatch_review import build_dispatch_review
from ..workflow_layer.live_adjudication_engine import run_live_adjudication
from ..workflow_layer.action_dispatch_review import build_action_dispatch_review
from app.services.data_residency_governance_service import data_residency_governance_service
from app.services.pricing_intelligence_governance_service import pricing_intelligence_governance_service
from app.services.tender_strategy_governance_service import tender_strategy_governance_service

DB_PATH = Path("runtime/workflow/workflow_layer.db")
DASHBOARD_PATH = Path("runtime/workflow/workflow_status_dashboard.json")
RFQ_SUMMARY_PATH = Path("runtime/rfqs/rfq_orchestration_summary.json")
ADJUDICATION_PATH = Path("runtime/adjudication/live_adjudication_summary.json")
ACTION_REVIEW_PATH = Path("runtime/adjudication/actions/action_dispatch_review.json")
QUOTE_INGESTION_PATH = Path("runtime/supplier_responses/quote_ingestion_summary.json")


app = FastAPI(
    title="LMCP AutoQuote API",
    version="2.0.0",
    description="Enterprise workflow API for RFQ, quote ingestion, adjudication and supplier communication."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_json(path, default):
    if not path.exists():
        return default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_table(table_name):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        cur.execute(f"SELECT * FROM {table_name}")
        rows = [dict(row) for row in cur.fetchall()]
    except Exception as exc:
        rows = {"error": str(exc)}
    finally:
        conn.close()

    return rows


@app.get("/")
def root():
    return {
        "system": "LMCP AutoQuote",
        "phase": "Phase 2B",
        "status": "API operational"
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "database_exists": DB_PATH.exists(),
        "dashboard_exists": DASHBOARD_PATH.exists()
    }


@app.get("/dashboard")
def dashboard():
    return load_json(DASHBOARD_PATH, {})


@app.get("/rfqs")
def rfqs():
    return load_json(RFQ_SUMMARY_PATH, [])


@app.get("/quotes")
def quotes():
    return load_json(QUOTE_INGESTION_PATH, {})


@app.get("/adjudication")
def adjudication():
    return load_json(ADJUDICATION_PATH, {})


@app.get("/actions")
def actions():
    return load_json(ACTION_REVIEW_PATH, {})


@app.get("/db/suppliers")
def db_suppliers():
    return fetch_table("supplier_contacts")


@app.get("/db/rfq-batches")
def db_rfq_batches():
    return fetch_table("rfq_batches")


@app.get("/db/supplier-responses")
def db_supplier_responses():
    return fetch_table("supplier_responses")


@app.get("/db/adjudication-decisions")
def db_adjudication_decisions():
    return fetch_table("adjudication_decisions")


@app.post("/refresh/dashboard")
def refresh_dashboard():
    return build_dashboard()


@app.post("/refresh/rfq-dispatch-review")
def refresh_rfq_dispatch_review():
    return build_dispatch_review()


@app.post("/refresh/adjudication")
def refresh_adjudication():
    return run_live_adjudication()


@app.post("/refresh/action-dispatch-review")
def refresh_action_dispatch_review():
    return build_action_dispatch_review()


@app.post("/refresh/all")
def refresh_all():
    rfq_review = build_dispatch_review()
    adjudication_result = run_live_adjudication()
    action_review = build_action_dispatch_review()
    dashboard_result = build_dashboard()

    return {
        "status": "refresh_complete",
        "rfq_review": rfq_review,
        "adjudication": adjudication_result,
        "action_review": action_review,
        "dashboard": dashboard_result
    }


@app.get("/rfq-lifecycle/data-residency-governance")
def data_residency_governance():
    return data_residency_governance_service.latest()


@app.get("/rfq-lifecycle/data-residency-governance/latest")
def data_residency_governance_latest():
    return data_residency_governance_service.latest()


@app.get("/rfq-lifecycle/data-residency-governance/history")
def data_residency_governance_history():
    return data_residency_governance_service.history()


@app.get("/rfq-lifecycle/pricing-intelligence")
def pricing_intelligence_governance():
    return pricing_intelligence_governance_service.list_pricing_intelligence()


@app.get("/rfq-lifecycle/pricing-intelligence/latest")
def pricing_intelligence_governance_latest():
    return pricing_intelligence_governance_service.latest_pricing_intelligence()


@app.get("/rfq-lifecycle/pricing-intelligence/history")
def pricing_intelligence_governance_history():
    return pricing_intelligence_governance_service.pricing_intelligence_history()


@app.get("/rfq-lifecycle/tender-strategy-governance")
def tender_strategy_governance():
    return tender_strategy_governance_service.list_tender_strategy_governance()


@app.get("/rfq-lifecycle/tender-strategy-governance/latest")
def tender_strategy_governance_latest():
    return tender_strategy_governance_service.latest_tender_strategy_governance()


@app.get("/rfq-lifecycle/tender-strategy-governance/history")
def tender_strategy_governance_history():
    return tender_strategy_governance_service.tender_strategy_governance_history()
