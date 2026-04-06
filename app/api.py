from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["LMCP AutoQuote"])


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.post("/harvest")
def run_harvest():
    try:
        from app.harvester import harvest_opportunities
        result = harvest_opportunities()
        return {
            "success": True,
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/harvest/departments")
def run_department_harvest():
    try:
        from app.department_harvester import harvest_department_rfqs
        result = harvest_department_rfqs()
        return {
            "success": True,
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/departments/seed")
def seed_departments():
    try:
        from app.database import SessionLocal
        from app.department_registry import DEPARTMENT_SOURCES
        from app.models import DepartmentSource

        db = SessionLocal()
        try:
            added = 0
            existing = 0

            for item in DEPARTMENT_SOURCES:
                row = (
                    db.query(DepartmentSource)
                    .filter(DepartmentSource.name == item["name"])
                    .first()
                )

                if row:
                    existing += 1
                    continue

                db.add(
                    DepartmentSource(
                        name=item["name"],
                        homepage_url=item["homepage_url"],
                        rfq_url=item["rfq_url"],
                        is_active=True,
                        notes=item.get("notes"),
                    )
                )
                added += 1

            db.commit()

            return {
                "success": True,
                "added": added,
                "existing": existing,
                "total_seed_items": len(DEPARTMENT_SOURCES),
            }
        finally:
            db.close()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/departments")
def list_departments():
    try:
        from app.database import SessionLocal
        from app.models import DepartmentSource

        db = SessionLocal()
        try:
            rows = (
                db.query(DepartmentSource)
                .order_by(DepartmentSource.name.asc())
                .all()
            )

            return [
                {
                    "id": row.id,
                    "name": row.name,
                    "homepage_url": row.homepage_url,
                    "rfq_url": row.rfq_url,
                    "is_active": row.is_active,
                    "last_checked_at": row.last_checked_at,
                    "last_success_at": row.last_success_at,
                }
                for row in rows
            ]
        finally:
            db.close()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/opportunities")
def list_opportunities():
    try:
        from app.database import SessionLocal
        from app.models import Opportunity

        db = SessionLocal()
        try:
            rows = (
                db.query(Opportunity)
                .order_by(Opportunity.id.desc())
                .limit(200)
                .all()
            )

            return [
                {
                    "id": row.id,
                    "source": row.source,
                    "external_id": row.external_id,
                    "title": row.title,
                    "status": row.status,
                    "score": row.score,
                    "category": row.category,
                    "preferred_sector": row.preferred_sector,
                    "review_status": row.review_status,
                    "decision_reason": row.decision_reason,
                    "source_url": row.source_url,
                    "document_url": row.document_url,
                }
                for row in rows
            ]
        finally:
            db.close()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/opportunities/review")
def list_review_queue():
    try:
        from app.database import SessionLocal
        from app.models import Opportunity

        db = SessionLocal()
        try:
            rows = (
                db.query(Opportunity)
                .filter(Opportunity.review_status == "manual_review")
                .order_by(Opportunity.id.desc())
                .limit(200)
                .all()
            )

            return [
                {
                    "id": row.id,
                    "title": row.title,
                    "score": row.score,
                    "category": row.category,
                    "decision_reason": row.decision_reason,
                    "source": row.source,
                }
                for row in rows
            ]
        finally:
            db.close()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/opportunities/{opportunity_id}/approve")
def approve_opportunity(opportunity_id: int):
    try:
        from app.database import SessionLocal
        from app.models import Opportunity
        from app.scoring import is_supply_delivery_opportunity

        db = SessionLocal()
        try:
            row = (
                db.query(Opportunity)
                .filter(Opportunity.id == opportunity_id)
                .first()
            )

            if not row:
                raise HTTPException(status_code=404, detail="Opportunity not found")

            if not is_supply_delivery_opportunity(row.title or "", row.description or ""):
                raise HTTPException(status_code=400, detail="Opportunity is not supply and delivery")

            row.review_status = "approved"
            row.decision_reason = f"Approved manually: {row.decision_reason or 'manual approval'}"
            db.commit()

            return {
                "success": True,
                "id": row.id,
                "review_status": row.review_status,
            }
        finally:
            db.close()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quotes/auto-build")
def auto_build_quotes_now():
    try:
        from app.tasks import auto_build_quotes
        result = auto_build_quotes()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
