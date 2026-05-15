
# LMCP Handwriting Glyph Engine

Copy files to:

```text
app/services/handwriting_glyph_service.py
app/api/handwriting_glyph_api.py
```

Add this line inside `OPTIONAL_ROUTERS` in `app/main.py`:

```python
("handwriting_glyph_router", "app.api.handwriting_glyph_api", "router"),
```

Ensure dependencies:

```bash
grep -qxF "pillow" requirements.txt || echo "pillow" >> requirements.txt
grep -qxF "reportlab" requirements.txt || echo "reportlab" >> requirements.txt
grep -qxF "PyPDF2" requirements.txt || echo "PyPDF2" >> requirements.txt
```

Rebuild:

```bash
docker compose up -d --build api
sleep 10
curl http://localhost:8000/handwriting-glyph/status
```

Build glyphs:

```bash
curl -X POST http://localhost:8000/handwriting-glyph/build-cache
```

Test:

```bash
curl -X POST http://localhost:8000/handwriting-glyph/overlay-existing-pdf \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_rfq_number":"TEST-GLYPH-HANDWRITING-001",
    "input_pdf":"runtime/test_tender_pack/RFQ 4254.pdf",
    "fields":[
      {"page":1,"x":120,"y":720,"text":"Lechesa Manaba Consulting and Projects Pty Ltd","glyph_height":14,"letter_spacing":1,"word_spacing":8,"max_width":380},
      {"page":1,"x":120,"y":695,"text":"Lechesa Manaba","glyph_height":15,"letter_spacing":1,"word_spacing":8},
      {"page":1,"x":120,"y":670,"text":"Director","glyph_height":15,"letter_spacing":1,"word_spacing":8}
    ]
  }'
```

Open:

```bash
open runtime/handwriting_simulation/glyph_form_outputs/TEST-GLYPH-HANDWRITING-001__glyph_handwritten_completed_form.pdf
```
