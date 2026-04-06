from fastapi import APIRouter
from app.services.pricing_schedule_service import PricingScheduleService

router = APIRouter(tags=["Test Pricing"])


@router.get("/test-pricing")
def test_pricing():
    rfq = {
        "title": "Supply and Delivery of Office Furniture",
        "buyer_name": "Department of Public Works",
        "rfq_number": "RFQ-2026-001",
        "currency": "ZAR",
        "vat_percent": 15,
        "default_markup_percent": 25,
        "quote_ready": True,
        "line_items": [
            {
                "line_no": "1",
                "description": "Supply and deliver office chair",
                "unit": "Each",
                "quantity": 20,
                "estimated_cost": 850.00,
            },
            {
                "line_no": "2",
                "description": "Supply and deliver executive desk",
                "unit": "Each",
                "quantity": 10,
                "estimated_cost": 3200.00,
            },
        ],
    }

    return PricingScheduleService.complete_buyer_pricing_schedule(rfq)
