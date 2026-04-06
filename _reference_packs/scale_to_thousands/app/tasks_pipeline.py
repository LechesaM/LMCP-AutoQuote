"""Pipeline tasks (stage-isolated)

These tasks are intentionally small and chained by IDs, so you can retry each stage safely.
"""

from celery import shared_task
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import Opportunity
from .soe_attach import attach_soe_match

@shared_task(name="app.tasks_pipeline.poll_etenders")
def poll_etenders():
    # Replace with real eTenders ingestion.
    # 1) fetch feed, 2) dedupe, 3) insert/update opportunities
    return {"ok": True}

@shared_task(name="app.tasks_pipeline.download_and_extract")
def download_and_extract(opportunity_id: int):
    db: Session = SessionLocal()
    try:
        opp = db.query(Opportunity).filter(Opportunity.id==opportunity_id).first()
        if not opp:
            return {"ok": False, "reason": "not_found"}
        # TODO: download docs -> object storage; extract RFQ spec into opp.rfq_spec
        attach_soe_match(db, opp)
        opp.status = "extracted"
        db.commit()
        return {"ok": True}
    finally:
        db.close()

@shared_task(name="app.tasks_pipeline.run_pricing")
def run_pricing(opportunity_id: int):
    db: Session = SessionLocal()
    try:
        opp = db.query(Opportunity).filter(Opportunity.id==opportunity_id).first()
        if not opp:
            return {"ok": False}
        # TODO: pricing engine
        opp.status = "priced"
        db.commit()
        return {"ok": True}
    finally:
        db.close()

@shared_task(name="app.tasks_pipeline.build_pack")
def build_pack(opportunity_id: int):
    db: Session = SessionLocal()
    try:
        opp = db.query(Opportunity).filter(Opportunity.id==opportunity_id).first()
        if not opp:
            return {"ok": False}
        # TODO: build master pack PDF + evidence zip
        opp.status = "ready_to_submit"
        db.commit()
        return {"ok": True}
    finally:
        db.close()

@shared_task(name="app.tasks_pipeline.gated_send")
def gated_send(opportunity_id: int):
    db: Session = SessionLocal()
    try:
        opp = db.query(Opportunity).filter(Opportunity.id==opportunity_id).first()
        if not opp:
            return {"ok": False}
        # TODO: policy gate + allowlist + MFA already validated in API prior to enqueue
        opp.status = "submitted"
        db.commit()
        return {"ok": True}
    finally:
        db.close()
