from fastapi import APIRouter
from datetime import datetime
from app.services.procurement_heatmap import build_procurement_heatmap
from app.services.adaptive_crawl_scheduler import build_adaptive_crawl_schedule
from app.services.autonomous_tender_hunter import rank_demo_opportunities
from app.services.portal_health_dashboard import build_portal_health_dashboard

router = APIRouter(tags=["System Routes"])


@router.get("/procurement-heatmap")
def procurement_heatmap():
    return build_procurement_heatmap()


@router.get("/adaptive-crawl-schedule")
def adaptive_crawl_schedule():
    return build_adaptive_crawl_schedule()


@router.get("/quotes")
def quotes():
    return []


@router.get("/opportunities")
def opportunities():
    return []


@router.get("/submissions")
def submissions():
    return []


@router.get("/scheduler/status")
def scheduler_status():
    return {
        "scheduler": "running",
        "last_cycle": datetime.utcnow().isoformat()
    }


@router.get("/scheduler/activity")
def scheduler_activity():
    return [
        {
            "task": "submission_pack_cycle",
            "status": "completed",
            "time": datetime.utcnow().isoformat()
        }
    ]


@router.get("/logs/recent")
def logs_recent():
    return {
        "logs": [
            "LMCP system started",
            "Scheduler running",
            "Control panel connected"
        ]
    }


@router.get("/autonomous-tender-hunter")
def autonomous_tender_hunter():
    return rank_demo_opportunities()


@router.get("/portal-health-dashboard")
def portal_health_dashboard():
    return build_portal_health_dashboard()
