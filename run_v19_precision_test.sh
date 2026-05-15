#!/bin/bash
set -e

echo "===================================================="
echo " LMCP AutoQuote — V19 Precision Engine One-Click Test"
echo "===================================================="

PROJECT_ROOT="/Users/Shared/LMCP-AutoQuote-Server"

echo ""
echo "1) Going to project root..."
cd "$PROJECT_ROOT"

echo ""
echo "2) Checking required V19 files..."

if [ ! -f "app/services/sbd_precision_engine_v19.py" ]; then
  echo "❌ Missing: app/services/sbd_precision_engine_v19.py"
  echo "Please copy sbd_precision_engine_v19.py into app/services/ first."
  exit 1
fi

if [ ! -f "app/api/sbd_intelligence_api.py" ]; then
  echo "❌ Missing: app/api/sbd_intelligence_api.py"
  echo "Please copy sbd_intelligence_api.py into app/api/ first."
  exit 1
fi

if ! grep -q "sbd_intelligence" "app/main.py"; then
  echo "❌ app/main.py does not include sbd_intelligence router."
  echo "Please replace app/main.py with the V19 corrected version first."
  exit 1
fi

echo "✅ Required V19 files found."

echo ""
echo "3) Checking Docker containers..."
docker compose ps

echo ""
echo "4) Checking PyMuPDF inside API container..."
docker compose exec api python - <<'PY'
try:
    import fitz
    print("✅ PyMuPDF OK")
except Exception as e:
    print("❌ PyMuPDF missing:", e)
    raise SystemExit(1)
PY

echo ""
echo "5) Checking PDF downloads folder inside Docker..."
docker compose exec api ls -lah "/app/runtime/playwright/downloads/" || true

echo ""
echo "6) Checking target PDF..."
TARGET_PDF="/app/runtime/playwright/downloads/RFQ  Corporate Gift Packs.pdf"

if docker compose exec api test -f "$TARGET_PDF"; then
  echo "✅ Target PDF found inside Docker:"
  docker compose exec api ls -lah "$TARGET_PDF"
else
  echo "❌ Target PDF not found:"
  echo "$TARGET_PDF"
  echo ""
  echo "Please confirm the exact PDF filename inside:"
  echo "runtime/playwright/downloads/"
  echo ""
  echo "Available files shown above."
  exit 1
fi

echo ""
echo "7) Restarting API..."
docker compose restart api
sleep 5

echo ""
echo "8) Testing /health..."
curl -s http://localhost:8000/health | python3 -m json.tool || curl http://localhost:8000/health

echo ""
echo "9) Testing V19 status..."
curl -s http://localhost:8000/sbd-intelligence/status | python3 -m json.tool || curl http://localhost:8000/sbd-intelligence/status

echo ""
echo "10) Running V19 completion..."
curl -s -X POST http://localhost:8000/sbd-intelligence/complete \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number":"TEST-V19-CORPORATE-GIFTS",
    "input_pdf":"runtime/playwright/downloads/RFQ  Corporate Gift Packs.pdf",
    "reference_image":"runtime/handwriting_simulation/clean_ink_cropped.png",
    "signature_image":"runtime/handwriting_simulation/signature.png",
    "ink_color":"black",
    "debug":true,
    "handwritten_mode":true,
    "buyer_name":"iSIMANGALISO WETLAND PARK AUTHORITY",
    "bid_description":"RFQ: APPOINTMENT OF SERVICE PROVIDER FOR PROCUREMENT OF CORPORATE GIFT PACKS"
  }' | python3 -m json.tool

echo ""
echo "11) Opening completed PDF if available..."
OUTPUT_PDF="runtime/sbd_intelligence/v19_outputs/TEST-V19-CORPORATE-GIFTS/TEST-V19-CORPORATE-GIFTS__v19_precision_completed.pdf"

if [ -f "$OUTPUT_PDF" ]; then
  echo "✅ Completed PDF created:"
  echo "$PROJECT_ROOT/$OUTPUT_PDF"
  open "$OUTPUT_PDF"
else
  echo "⚠️ Completed PDF not found at expected path:"
  echo "$PROJECT_ROOT/$OUTPUT_PDF"
  echo "Check the JSON response above for the exact output_pdf path."
fi

echo ""
echo "===================================================="
echo " V19 one-click test finished."
echo "===================================================="
