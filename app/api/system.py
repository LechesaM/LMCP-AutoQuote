from fastapi import APIRouter
from app.services.portal_radar_service import get_portal_radar_cache, get_portal_radar_summary
from app.services.procurement_heatmap import get_procurement_heatmap, build_procurement_heatmap
from app.services.adaptive_crawl_scheduler import build_adaptive_crawl_schedule
from app.services.procurement_heatmap import build_procurement_heatmap
from app.services.portal_health_dashboard import build_portal_health_dashboard

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/health")
def system_health():
    portal_radar = get_portal_radar_summary()

    return {
        "system": "LMCP AutoQuote",
        "status": "ok",
        "portal_radar": portal_radar,
    }

@router.get("/portal-health")
def system_portal_health():
    return get_portal_radar_cache()

@router.get("/procurement-heatmap")
def procurement_heatmap():
    return build_procurement_heatmap()

@router.get("/adaptive-crawl-schedule")
def adaptive_crawl_schedule():
    return build_adaptive_crawl_schedule()

@router.get("/portal-health-dashboard")
def portal_health_dashboard():
    return build_portal_health_dashboard()
