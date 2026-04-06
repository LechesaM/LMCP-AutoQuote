from datetime import datetime
from decimal import Decimal


def build_quote_for_opportunity(opportunity_id: int):
    from app.database import SessionLocal
    from app.models import Opportunity, QuoteDraft, QuoteLineItem
    from app.scoring import is_supply_delivery_opportunity

    db = SessionLocal()

    try:
        opportunity = (
            db.query(Opportunity)
            .filter(Opportunity.id == opportunity_id)
            .first()
        )

        if not opportunity:
            return {"success": False, "message": "Opportunity not found"}

        if not is_supply_delivery_opportunity(opportunity.title or "", opportunity.description or ""):
            return {"success": False, "message": "Opportunity is not supply and delivery"}

        if opportunity.review_status != "approved":
            return {"success": False, "message": "Opportunity is not approved for auto-quote"}

        existing_quote = (
            db.query(QuoteDraft)
            .filter(QuoteDraft.opportunity_id == opportunity.id)
            .first()
        )

        if existing_quote:
            return {
                "success": True,
                "message": "Quote already exists",
                "quote_id": existing_quote.id,
            }

        quote_number = f"LMCP-AUTO-{opportunity.id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        quote = QuoteDraft(
            opportunity_id=opportunity.id,
            quote_number=quote_number,
            created_at=datetime.utcnow(),
            status="draft",
            total_amount=Decimal("0.00"),
        )
        db.add(quote)
        db.flush()

        title_text = opportunity.title.strip() if opportunity.title else "Supply Item"

        default_price = Decimal("1000.00")
        quantity = Decimal("1.00")
        line_total = default_price * quantity

        line = QuoteLineItem(
            quote_id=quote.id,
            description=title_text[:500],
            quantity=quantity,
            unit_price=default_price,
            line_total=line_total,
        )
        db.add(line)

        quote.total_amount = line_total
        opportunity.status = "quoted"

        db.commit()

        return {
            "success": True,
            "quote_id": quote.id,
            "quote_number": quote.quote_number,
            "total_amount": float(quote.total_amount),
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "message": str(e)}
    finally:
        db.close()
