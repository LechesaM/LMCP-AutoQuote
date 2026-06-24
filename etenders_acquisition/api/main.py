import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services.historical_learning_service import HistoricalLearningService
from app.services.vector_intelligence_service import VectorIntelligenceService
from app.services.production_hardening_readiness_service import ProductionHardeningReadinessService
from etenders_acquisition.workflow_layer.workflow_status_dashboard import build_dashboard
from etenders_acquisition.workflow_layer.rfq_dispatch_review import build_dispatch_review
from etenders_acquisition.workflow_layer.live_adjudication_engine import run_live_adjudication
from etenders_acquisition.workflow_layer.action_dispatch_review import build_action_dispatch_review


DB_PATH = Path("runtime/workflow/workflow_layer.db")
DASHBOARD_PATH = Path("runtime/workflow/workflow_status_dashboard.json")
RFQ_SUMMARY_PATH = Path("runtime/rfqs/rfq_orchestration_summary.json")
ADJUDICATION_PATH = Path("runtime/adjudication/live_adjudication_summary.json")
ACTION_REVIEW_PATH = Path("runtime/adjudication/actions/action_dispatch_review.json")
QUOTE_INGESTION_PATH = Path("runtime/supplier_responses/quote_ingestion_summary.json")


app = FastAPI(
    title="LMCP AutoQuote API",
    version="2.0.0",
    description="Enterprise workflow API for RFQ, quote ingestion, adjudication and supplier communication.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        return {"status": "error", "path": str(path), "error": str(exc)}


def fetch_table(table_name: str) -> Any:
    if not DB_PATH.exists():
        return {"status": "error", "error": f"Database not found: {DB_PATH}"}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        cur.execute(f"SELECT * FROM {table_name}")
        return [dict(row) for row in cur.fetchall()]
    except Exception as exc:
        return {"status": "error", "table": table_name, "error": str(exc)}
    finally:
        conn.close()


def safe_run(fn: Callable, fallback_name: str) -> Any:
    try:
        return fn()
    except Exception as exc:
        return {
            "status": "partial",
            "module": fallback_name,
            "error": str(exc),
        }


def not_available(module_name: str) -> dict:
    return {
        "status": "not_available",
        "module": module_name,
        "reason": "Service module is not present in app/services in this project structure.",
    }


def production_hardening_readiness_service() -> ProductionHardeningReadinessService:
    return ProductionHardeningReadinessService()


def historical_learning_service() -> HistoricalLearningService:
    return HistoricalLearningService()


def vector_intelligence_service() -> VectorIntelligenceService:
    return VectorIntelligenceService()


@app.get("/")
def root():
    return {
        "system": "LMCP AutoQuote",
        "phase": "Phase 2B",
        "status": "API operational",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "database_exists": DB_PATH.exists(),
        "dashboard_exists": DASHBOARD_PATH.exists(),
    }


@app.get("/system/status")
def system_status():
    return {
        "status": "healthy",
        "backend": "online",
        "service": "LMCP AutoQuote API",
        "database_exists": DB_PATH.exists(),
        "dashboard_exists": DASHBOARD_PATH.exists(),
    }


@app.get("/dashboard")
def dashboard():
    return load_json(DASHBOARD_PATH, {})


@app.get("/api/dashboard")
def api_dashboard():
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
    return safe_run(build_dashboard, "workflow_status_dashboard")


@app.post("/refresh/rfq-dispatch-review")
def refresh_rfq_dispatch_review():
    return safe_run(build_dispatch_review, "rfq_dispatch_review")


@app.post("/refresh/adjudication")
def refresh_adjudication():
    return safe_run(run_live_adjudication, "live_adjudication_engine")


@app.post("/refresh/action-dispatch-review")
def refresh_action_dispatch_review():
    return safe_run(build_action_dispatch_review, "action_dispatch_review")


@app.post("/refresh/all")
def refresh_all():
    return {
        "status": "refresh_complete",
        "rfq_review": safe_run(build_dispatch_review, "rfq_dispatch_review"),
        "adjudication": safe_run(run_live_adjudication, "live_adjudication_engine"),
        "action_review": safe_run(build_action_dispatch_review, "action_dispatch_review"),
        "dashboard": safe_run(build_dashboard, "workflow_status_dashboard"),
    }


@app.get("/rfq-lifecycle/data-residency-governance")
def data_residency_governance():
    return not_available("data_residency_governance_service")


@app.get("/rfq-lifecycle/data-residency-governance/latest")
def data_residency_governance_latest():
    return not_available("data_residency_governance_service")


@app.get("/rfq-lifecycle/data-residency-governance/history")
def data_residency_governance_history():
    return not_available("data_residency_governance_service")


@app.get("/rfq-lifecycle/pricing-intelligence")
def pricing_intelligence_governance():
    return not_available("pricing_intelligence_governance_service")


@app.get("/rfq-lifecycle/pricing-intelligence/latest")
def pricing_intelligence_governance_latest():
    return not_available("pricing_intelligence_governance_service")


@app.get("/rfq-lifecycle/pricing-intelligence/history")
def pricing_intelligence_governance_history():
    return not_available("pricing_intelligence_governance_service")


@app.get("/rfq-lifecycle/tender-strategy-governance")
def tender_strategy_governance():
    return not_available("tender_strategy_governance_service")


@app.get("/rfq-lifecycle/tender-strategy-governance/latest")
def tender_strategy_governance_latest():
    return not_available("tender_strategy_governance_service")


@app.get("/rfq-lifecycle/tender-strategy-governance/history")
def tender_strategy_governance_history():
    return not_available("tender_strategy_governance_service")


@app.get("/rfq-lifecycle/executive-decision-workspace")
def executive_decision_workspace():
    return not_available("executive_decision_workspace_service")


@app.get("/rfq-lifecycle/executive-decision-workspace/latest")
def executive_decision_workspace_latest():
    return not_available("executive_decision_workspace_service")


@app.get("/rfq-lifecycle/executive-decision-workspace/history")
def executive_decision_workspace_history():
    return not_available("executive_decision_workspace_service")


@app.get("/rfq-lifecycle/historical-learning")
def historical_learning():
    return historical_learning_service().latest_historical_learning()


@app.get("/rfq-lifecycle/historical-learning/latest")
def historical_learning_latest():
    return historical_learning_service().latest_historical_learning()


@app.get("/rfq-lifecycle/historical-learning/history")
def historical_learning_history():
    return historical_learning_service().historical_learning_history()


@app.get("/rfq-lifecycle/vector-intelligence")
def vector_intelligence():
    return vector_intelligence_service().latest_vector_intelligence()


@app.get("/rfq-lifecycle/vector-intelligence/latest")
def vector_intelligence_latest():
    return vector_intelligence_service().latest_vector_intelligence()


@app.get("/rfq-lifecycle/vector-intelligence/history")
def vector_intelligence_history():
    return vector_intelligence_service().vector_intelligence_history()


@app.get("/rfq-lifecycle/controlled-automation-orchestration")
def controlled_automation_orchestration():
    return not_available("controlled_automation_orchestration_service")


@app.get("/rfq-lifecycle/controlled-automation-orchestration/latest")
def controlled_automation_orchestration_latest():
    return not_available("controlled_automation_orchestration_service")


@app.get("/rfq-lifecycle/controlled-automation-orchestration/history")
def controlled_automation_orchestration_history():
    return not_available("controlled_automation_orchestration_service")


@app.get("/rfq-lifecycle/production-hardening-readiness")
def production_hardening_readiness():
    return production_hardening_readiness_service().latest_production_hardening_readiness()


@app.get("/rfq-lifecycle/production-hardening-readiness/latest")
def production_hardening_readiness_latest():
    return production_hardening_readiness_service().latest_production_hardening_readiness()


@app.get("/rfq-lifecycle/production-hardening-readiness/history")
def production_hardening_readiness_history():
    return production_hardening_readiness_service().production_hardening_readiness_history()
