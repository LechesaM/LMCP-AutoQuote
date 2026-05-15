#!/bin/bash
set -e

PROJECT_ROOT="/Users/Shared/LMCP-AutoQuote-Server"
cd "$PROJECT_ROOT"

echo "===================================================="
echo " LMCP AutoQuote — V20.1.1 Coordinate-Fixed Writer Test"
echo "===================================================="

echo ""
echo "1) Restarting API..."
docker compose restart api
sleep 5

echo ""
echo "2) Status..."
curl -s http://localhost:8000/sbd-intelligence/status | python3 -m json.tool

echo ""
echo "3) Running coordinate-fixed completion..."
curl -s -X POST http://localhost:8000/sbd-intelligence/complete \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number":"TEST-V20-1-1-CORPORATE-GIFTS",
    "input_pdf":"runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
    "signature_image":"runtime/handwriting_simulation/signature.png",
    "debug":true,
    "handwritten_mode":true,
    "buyer_name":"iSIMANGALISO WETLAND PARK AUTHORITY",
    "bid_description":"RFQ: APPOINTMENT OF SERVICE PROVIDER FOR PROCUREMENT OF CORPORATE GIFT PACKS"
  }' | tee /tmp/lmcp_v20_1_1_result.json | python3 -m json.tool

OUTPUT="runtime/handwriting_simulation/v20_clean_writer_outputs/TEST-V20-1-1-CORPORATE-GIFTS/TEST-V20-1-1-CORPORATE-GIFTS__v20_1_1_coordinate_fixed_completed.pdf"

echo ""
if [ -f "$OUTPUT" ]; then
  echo "✅ Opening coordinate-fixed PDF:"
  open "$OUTPUT"
else
  echo "⚠️ Output not found. Search:"
  find runtime -name "*TEST-V20-1-1*" | sort || true
fi

echo "===================================================="

