# LMCP V50.7 Upgrade - eTenders Detail Navigation + Verified RFQ Promotion

## Files to copy

Copy these into your project root:

```bash
cp lmcp_v50_7_etenders_detail_and_promotion/app/services/etenders_real_detail_navigation_v50_7_service.py app/services/
cp lmcp_v50_7_etenders_detail_and_promotion/app/services/verified_rfq_promotion_gate_v50_7_service.py app/services/

cp lmcp_v50_7_etenders_detail_and_promotion/app/api/etenders_real_detail_navigation_v50_7_api.py app/api/
cp lmcp_v50_7_etenders_detail_and_promotion/app/api/verified_rfq_promotion_gate_v50_7_api.py app/api/
```

## Add routers to app/main.py

Add imports:

```python
from app.api.etenders_real_detail_navigation_v50_7_api import router as etenders_real_detail_navigation_v50_7_router
from app.api.verified_rfq_promotion_gate_v50_7_api import router as verified_rfq_promotion_gate_v50_7_router
```

Add includes near your other router includes:

```python
app.include_router(etenders_real_detail_navigation_v50_7_router)
app.include_router(verified_rfq_promotion_gate_v50_7_router)
```

## Compile and restart

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

python3 -m py_compile app/services/etenders_real_detail_navigation_v50_7_service.py
python3 -m py_compile app/services/verified_rfq_promotion_gate_v50_7_service.py
python3 -m py_compile app/api/etenders_real_detail_navigation_v50_7_api.py
python3 -m py_compile app/api/verified_rfq_promotion_gate_v50_7_api.py
python3 -m py_compile app/main.py

docker compose restart api
sleep 8

curl http://localhost:8000/v50-7-etenders-navigation/status
curl http://localhost:8000/v50-7-promotion-gate/status
```

## Test eTenders navigation

```bash
curl -X POST http://localhost:8000/v50-7-etenders-navigation/analyse \
  -H "Content-Type: application/json" \
  -d '{
    "title":"SUPPLY AND DELIVERY OF STATIONERY 08/05/2026 in 7 days",
    "buyer_rfq_number":"SUPPLY AND DELIVERY OF STATIONERY 08/05/2026 in 7 days",
    "source_url":"https://www.etenders.gov.za/Home/opportunities",
    "document_url":"https://www.etenders.gov.za/Home/opportunities"
  }'
```

Expected improvement:
- generic listing URLs should be down-scored
- weak DownloadSpec links should not be promoted
- safe_to_download should remain false unless a specific tender document is matched

## Test verified promotion gate

```bash
curl -X POST http://localhost:8000/v50-7-promotion-gate/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "policy": {
      "minimum_profit_required": 30000,
      "min_confidence": 0.35,
      "allow_email_send": false,
      "allow_portal_upload": true,
      "allow_portal_final_submit": false
    },
    "item": {
      "title": "Supply and delivery of Steel drums to Necsa for a period of 3 years.",
      "buyer_rfq_number": "FIN-SCM-TEN-0216",
      "eligible": true,
      "quote_ready": true,
      "estimated_profit": 1536666.66,
      "ai_score": 65,
      "submission_method": "portal",
      "quantity_safety_status": "verified_buyer_docx_quantities",
      "quantity_source": "buyer_docx_main_document",
      "line_items": [
        {
          "description": "DRUM, METAL; 160L",
          "quantity": 5000,
          "unit": "EACH",
          "source": "buyer_docx_main_document",
          "docx_confidence": 0.995
        }
      ]
    }
  }'
```

Expected result:
- promotion_allowed: true
- submission_gate_allowed: true
- final_submit_gate_allowed: false
- next_action: prepare_portal_submission_pack

## Recommended next wiring

In the autonomous radar after document extraction/pricing, call:

```python
from app.services.verified_rfq_promotion_gate_v50_7_service import evaluate_verified_rfq_for_promotion

promotion = evaluate_verified_rfq_for_promotion(item, auto_submission_policy)
item["v50_7_promotion_gate"] = promotion
item["auto_submission_gate_allowed"] = promotion["submission_gate_allowed"]
item["auto_submission_gate_reason"] = ",".join(promotion["blockers"]) or promotion["next_action"]
```

For eTenders items before document acquisition, call:

```python
from app.services.etenders_real_detail_navigation_v50_7_service import analyse_etenders_detail_navigation

nav = analyse_etenders_detail_navigation(item)
item["v50_7_etenders_navigation"] = nav

if nav["safe_to_download"]:
    item["document_url"] = nav["recommended_document_links"][0]["url"]
elif nav["recommended_detail_links"]:
    item["detail_url"] = nav["recommended_detail_links"][0]["url"]
else:
    item["pipeline_status"] = "detail_navigation_required"
    item["quote_ready"] = False
```

This keeps eTenders safe while allowing portals like NECSA to move faster when buyer quantities are verified.
