from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

try:
    from fastapi.templating import Jinja2Templates
except Exception:  # pragma: no cover
    Jinja2Templates = None  # type: ignore[assignment]

from app.celery_app import (
    SCHEDULED_TENDER_HARVEST_BEAT_INTERVAL_MINUTES,
    SCHEDULED_TENDER_HARVEST_DURATION_MINUTES,
)
from app.services.tender_harvester import (
    HARVEST_AUTO_SUBMIT_MINIMUM_AI_SCORE,
    HARVEST_MINIMUM_AI_SCORE,
)

router = APIRouter(tags=["Control Panel UI"])

if Jinja2Templates is not None:
    try:
        templates = Jinja2Templates(directory="app/templates")
    except Exception:  # pragma: no cover
        templates = None
else:
    templates = None
CONTROL_PANEL_TEMPLATE = Path(__file__).resolve().parent / "templates" / "control_panel.html"


def _render_control_panel(request: Request):
    context = {
        "request": request,
        "harvest_minimum_ai_score": HARVEST_MINIMUM_AI_SCORE,
        "harvest_auto_submit_minimum_ai_score": HARVEST_AUTO_SUBMIT_MINIMUM_AI_SCORE,
        "scheduled_harvest_beat_interval_minutes": SCHEDULED_TENDER_HARVEST_BEAT_INTERVAL_MINUTES,
        "scheduled_harvest_duration_minutes": SCHEDULED_TENDER_HARVEST_DURATION_MINUTES,
    }

    if templates is not None:
        return templates.TemplateResponse("control_panel.html", context)

    rendered = CONTROL_PANEL_TEMPLATE.read_text(encoding="utf-8")
    rendered = rendered.replace("{{ harvest_minimum_ai_score }}", str(context["harvest_minimum_ai_score"]))
    rendered = rendered.replace("{{ harvest_auto_submit_minimum_ai_score }}", str(context["harvest_auto_submit_minimum_ai_score"]))
    rendered = rendered.replace("{{ scheduled_harvest_beat_interval_minutes }}", str(context["scheduled_harvest_beat_interval_minutes"]))
    rendered = rendered.replace("{{ scheduled_harvest_duration_minutes }}", str(context["scheduled_harvest_duration_minutes"]))
    return HTMLResponse(rendered)


@router.get("/", response_class=HTMLResponse)
def control_panel_home(request: Request):
    return _render_control_panel(request)


@router.get("/control-panel", response_class=HTMLResponse)
def control_panel(request: Request):
    return _render_control_panel(request)
