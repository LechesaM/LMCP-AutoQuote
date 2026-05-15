
# LMCP V21 Real Handwriting Engine

This package fixes the core issue: the system must stop typing into forms and must instead overlay transparent handwriting ink images onto the PDF.

## Files included

- `app/services/tender_form_intelligence_engine.py`
- `app/api/tender_form_intelligence_api.py`

## Install / replace

From project root:

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp app/services/tender_form_intelligence_engine.py app/services/tender_form_intelligence_engine.py.bak.$(date +%Y%m%d%H%M%S) 2>/dev/null || true
cp app/api/tender_form_intelligence_api.py app/api/tender_form_intelligence_api.py.bak.$(date +%Y%m%d%H%M%S) 2>/dev/null || true

cp ~/Downloads/lmcp_v21_handwriting_engine/app/services/tender_form_intelligence_engine.py app/services/tender_form_intelligence_engine.py
cp ~/Downloads/lmcp_v21_handwriting_engine/app/api/tender_form_intelligence_api.py app/api/tender_form_intelligence_api.py
```

If you unzip directly into the project:

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v21_handwriting_engine.zip -d .
```

## Make sure requirements exist

Inside your API container:

```bash
docker compose exec api pip install pymupdf pillow
```

## Restart

```bash
docker compose restart api
sleep 5
curl http://localhost:8000/sbd-intelligence/status
```

Expected:

```json
{
  "status": "ok",
  "engine_version": "V21_REAL_HANDWRITING_OVERLAY",
  "typed_pdf_text_disabled": true
}
```

## Test

Use a PDF path that actually exists in your project. First check:

```bash
find runtime -iname "*.pdf" | head -20
```

Then run:

```bash
curl -X POST http://localhost:8000/sbd-intelligence/complete \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number":"TEST-V21-HANDWRITING",
    "input_pdf":"runtime/playwright/downloads/RFQ Corporate Gift Packs.pdf",
    "reference_image":"runtime/handwriting_simulation/clean_ink_cropped.png",
    "signature_image":"runtime/handwriting_simulation/signature.png",
    "ink_color":"black",
    "debug":true,
    "buyer_name":"iSIMANGALISO WETLAND PARK AUTHORITY",
    "bid_description":"RFQ: APPOINTMENT OF SERVICE PROVIDER FOR PROCUREMENT OF CORPORATE GIFT PACKS",
    "fields":[
      {
        "page":1,
        "x":120,
        "y":720,
        "w":360,
        "h":30,
        "text":"Lechesa Manaba Consulting and Projects (Pty) Ltd",
        "name":"company_name",
        "font_size":15
      },
      {
        "page":1,
        "x":120,
        "y":690,
        "w":220,
        "h":30,
        "text":"Lechesa Manaba",
        "name":"director_name",
        "font_size":15
      },
      {
        "page":1,
        "x":120,
        "y":660,
        "w":180,
        "h":30,
        "text":"Director",
        "name":"designation",
        "font_size":15
      }
    ]
  }'
```

Open output:

```bash
open runtime/tender_form_intelligence/completed_forms/TEST-V21-HANDWRITING__v21_real_handwritten_completed_form.pdf
```

## Important

This V21 engine does not use typed PDF text insertion. Every field is converted to transparent ink image first, then inserted into the PDF.
