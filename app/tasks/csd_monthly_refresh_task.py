from __future__ import annotations

"""
Optional Celery-compatible task wrapper for V25 CSD Monthly Refresh.

Drop-in path:
    app/tasks/csd_monthly_refresh_task.py
"""

from app.services.csd_monthly_refresh_service import run_monthly_csd_refresh_if_due


def run_csd_monthly_refresh_task():
    return run_monthly_csd_refresh_if_due()

