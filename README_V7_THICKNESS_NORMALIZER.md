# LMCP Handwriting V7 Thickness Normalizer

This upgrade normalizes stroke weight so thin handwriting lines look closer to the thicker name/signature line.

## 1. Copy file

```bash
cp app/services/handwriting_thickness_normalizer_v7.py /Users/Shared/LMCP-AutoQuote-Server/app/services/
```

## 2. Patch service

Open:

```bash
nano app/services/handwriting_simulation_service.py
```

Replace your existing `_draw_line_ink(...)` function with the version in:

```text
PATCH_replace_draw_line_ink.txt
```

## 3. Restart

```bash
docker compose restart api
sleep 5
```

## 4. Normalize existing line assets manually

```bash
python3 - <<'PY'
from app.services.handwriting_thickness_normalizer_v7 import normalize_line_ink_job_v7
import json
print(json.dumps(normalize_line_ink_job_v7(job_id="REAL-HANDWRITING"), indent=2))
PY
```

## 5. Test overlay with normalization enabled

```bash
curl -X POST http://localhost:8000/handwriting-simulation/overlay \
-H "Content-Type: application/json" \
-d '{
  "buyer_rfq_number":"TEST-V7-NORMALIZED",
  "page_size":"A4",
  "style":{
    "auto_map_fields":true,
    "use_line_ink":true,
    "line_ink_job_id":"REAL-HANDWRITING",
    "normalize_ink_thickness":true,
    "normalized_target_density":0.075,
    "normalized_darken_factor":0.78,
    "fallback_to_font":true
  },
  "fields":[
    {"page":1,"x":120,"y":720,"field_name":"Full Name","text":"Lechesa Manaba","line_index":1,"scale":1.0},
    {"page":1,"x":120,"y":660,"field_name":"Designation","text":"Director","line_index":2,"scale":1.1},
    {"page":1,"x":120,"y":600,"field_name":"Company Name","text":"Lechesa Manaba Consulting and Projects (Pty) Ltd","mode":"dynamic","dynamic_font_size":22}
  ]
}'
```

Open:

```bash
open runtime/handwriting_simulation/outputs/TEST-V7-NORMALIZED__handwriting_overlay.pdf
```

Normalized files will be saved here:

```text
runtime/handwriting_simulation/normalized_ink_v7/REAL-HANDWRITING/
```
