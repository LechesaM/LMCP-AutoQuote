from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["Control Panel UI"])

templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def control_panel_home(request: Request):
    return templates.TemplateResponse("control_panel.html", {"request": request})


@router.get("/control-panel", response_class=HTMLResponse)
def control_panel(request: Request):
    return templates.TemplateResponse("control_panel.html", {"request": request})
