#!/bin/bash
set -e

PROJECT_ROOT="/Users/Shared/LMCP-AutoQuote-Server"
cd "$PROJECT_ROOT"

echo "===================================================="
echo " LMCP AutoQuote — V20 Field Mapping Engine Test"
echo "===================================================="

echo ""
echo "1) Checking V20 files..."
test -f app/services/sbd_field_mapping_engine_v20.py || { echo "Missing app/services/sbd_field_mapping_engine_v20.py"; exit 1; }
test -f app/api/sbd_intelligence_api.py || { echo "Missing app/api/sbd_intelligence_api.py"; exit 1; }

echo "✅ V20 files found"

echo ""
echo "2) Restarting API..."
docker compose restart api
sleep 5

echo ""
echo "3) V20 status..."
curl -s http://localhost:8000/sbd-intelligence/status | python3 -m json.tool

echo ""
echo "4) Checking downloads folder..."
docker compose exec -T api ls -lah "/app/runtime/playwright/downloads/"

echo ""
echo "5) Running V20 completion..."
curl -s -X POST http://localhost:8000/sbd-intelligence/complete \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number":"TEST-V20-CORPORATE-GIFTS",
    "input_pdf":"runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
    "debug":true,
    "handwritten_mode":true,
    "buyer_name":"iSIMANGALISO WETLAND PARK AUTHORITY",
    "bid_description":"RFQ: APPOINTMENT OF SERVICE PROVIDER FOR PROCUREMENT OF CORPORATE GIFT PACKS"
  }' | tee /tmp/lmcp_v20_result.json | python3 -m json.tool

echo ""
echo "6) Finding V20/V18 outputs..."
find runtime -name "*TEST-V20*" -o -name "*v20_field_mapping_manifest.json" | sort || true

echo ""
echo "Open the output_pdf shown in the JSON above."
echo "===================================================="

