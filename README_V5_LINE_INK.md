# LMCP Handwriting V5 Line Ink Corrected

This fixes the issue where the full handwriting block is repeated.

It splits the real handwriting into line PNGs and places the correct line per field.

Copy files:

```bash
cp app/services/handwriting_line_ink_v5.py /Users/Shared/LMCP-AutoQuote-Server/app/services/
cp app/services/handwriting_simulation_service.py /Users/Shared/LMCP-AutoQuote-Server/app/services/
```

Restart:

```bash
docker compose restart api
sleep 5
curl http://localhost:8000/handwriting-simulation/status
```

Build line assets manually:

```bash
python3 - <<'PY'
from app.services.handwriting_line_ink_v5 import build_line_ink_assets_v5
import json
print(json.dumps(build_line_ink_assets_v5(job_id="REAL-HANDWRITING"), indent=2))
PY
```

Test:

```bash
curl -X POST http://localhost:8000/handwriting-simulation/overlay \
-H "Content-Type: application/json" \
-d '{
  "buyer_rfq_number":"TEST-V5-LINE-INK-001",
  "page_size":"A4",
  "style":{
    "use_line_ink":true,
    "line_ink_job_id":"REAL-HANDWRITING",
    "fallback_to_font":false,
    "line_ink_max_width":420,
    "line_ink_max_height":55
  },
  "fields":[
    {"page":1,"x":120,"y":720,"text":"Lechesa Manaba","line_index":1},
    {"page":1,"x":120,"y":660,"text":"Director","line_index":2},
    {"page":1,"x":120,"y":600,"text":"Lechesa Manaba Consulting and Projects (Pty) Ltd","line_index":3}
  ]
}'
```

Open:

```bash
open runtime/handwriting_simulation/outputs/TEST-V5-LINE-INK-001__handwriting_overlay.pdf
```
