# LMCP V40 Clickable Navigation Extractor

This package adds a safe V40 router and service without replacing your V39 files.

## Files included

Copy these into your project:

```bash
cp lmcp_v40_clickable_navigation_extractor/app/services/clickable_navigation_v40_service.py app/services/clickable_navigation_v40_service.py
cp lmcp_v40_clickable_navigation_extractor/app/api/clickable_navigation_v40_api.py app/api/clickable_navigation_v40_api.py
```

## Install dependency if missing

```bash
docker compose exec api pip install pymupdf
```

If your image already has PyMuPDF / fitz, you can skip that.

## Wire into app/main.py

Add this import near your other router imports:

```python
from app.api.clickable_navigation_v40_api import router as clickable_navigation_v40_router
```

Add this include near your other `app.include_router(...)` lines:

```python
app.include_router(clickable_navigation_v40_router)
```

## Restart and test

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

python3 -m py_compile app/services/clickable_navigation_v40_service.py
python3 -m py_compile app/api/clickable_navigation_v40_api.py
python3 -m py_compile app/main.py

docker compose restart api
sleep 8

curl http://localhost:8000/v40-clickable-navigation/status
```

## Run extraction test

Replace the PDF path with one that exists in your system:

```bash
curl -X POST http://localhost:8000/v40-clickable-navigation/extract \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number": "TEST-V40-NAV",
    "input_pdf": "runtime/playwright/downloads/RFQ  Corporate Gift Packs.pdf",
    "max_pages_scan": 10,
    "include_low_confidence": true
  }'
```

Expected output:

```json
{
  "status": "ok",
  "service_version": "V40_CLICKABLE_NAVIGATION_EXTRACTOR",
  "summary": {
    "total_items": 0
  },
  "items": []
}
```

If the PDF contains clickable annotations, bookmarks, TOC-like page text, links or email links, `items` will contain extracted navigation rows.
