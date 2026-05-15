#!/bin/bash
set -e

PROJECT_ROOT="/Users/Shared/LMCP-AutoQuote-Server"
cd "$PROJECT_ROOT"

echo "===================================================="
echo " LMCP AutoQuote — V20.1 Clean Writer Engine Test"
echo "===================================================="

echo ""
echo "1) Checking V20.1 files..."
test -f app/services/sbd_field_mapping_engine_v20.py || { echo "Missing app/services/sbd_field_mapping_engine_v20.py"; exit 1; }
test -f app/api/sbd_intelligence_api.py || { echo "Missing app/api/sbd_intelligence_api.py"; exit 1; }

echo "✅ V20.1 files found"

echo ""
echo "2) Restarting API..."
docker compose restart api
sleep 5

echo ""
echo "3) V20.1 status..."
curl -s http://localhost:8000/sbd-intelligence/status | python3 -m json.tool

echo ""
echo "4) Running V20.1 completion..."
curl -s -X POST http://localhost:8000/sbd-intelligence/complete \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number":"TEST-V20-1-CORPORATE-GIFTS",
    "input_pdf":"runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
    "signature_image":"runtime/handwriting_simulation/signature.png",
    "debug":true,
    "handwritten_mode":true,
    "buyer_name":"iSIMANGALISO WETLAND PARK AUTHORITY",
    "bid_description":"RFQ: APPOINTMENT OF SERVICE PROVIDER FOR PROCUREMENT OF CORPORATE GIFT PACKS"
  }' | tee /tmp/lmcp_v20_1_result.json | python3 -m json.tool

echo ""
echo "5) Finding V20.1 outputs..."
find runtime -name "*TEST-V20-1*" | sort || true

OUTPUT="runtime/handwriting_simulation/v20_clean_writer_outputs/TEST-V20-1-CORPORATE-GIFTS/TEST-V20-1-CORPORATE-GIFTS__v20_1_clean_writer_completed.pdf"

echo ""
if [ -f "$OUTPUT" ]; then
  echo "✅ Opening V20.1 clean writer PDF:"
  echo "$OUTPUT"
  open "$OUTPUT"
else
  echo "⚠️ Expected output not found. Check output_pdf in JSON above."
fi

echo "===================================================="

