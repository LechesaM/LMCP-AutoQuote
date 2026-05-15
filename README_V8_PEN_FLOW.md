# LMCP Handwriting V8 Pen Flow Variation

## Copy file

```bash
cp app/services/handwriting_pen_flow_v8.py /Users/Shared/LMCP-AutoQuote-Server/app/services/
```

## Patch service

Open:

```bash
nano app/services/handwriting_simulation_service.py
```

Replace the existing `_draw_line_ink(...)` function with the version in:

```text
PATCH_replace_draw_line_ink_for_v8.txt
```

## Restart

```bash
docker compose restart api
sleep 5
```

## Build V8 assets

```bash
python3 - <<'PY'
from app.services.handwriting_pen_flow_v8 import apply_pen_flow_to_job_v8
import json
print(json.dumps(apply_pen_flow_to_job_v8(job_id="REAL-HANDWRITING"), indent=2))
PY
```

Check:

```bash
ls runtime/handwriting_simulation/pen_flow_v8/REAL-HANDWRITING
```

## Test overlay

```bash
curl -X POST http://localhost:8000/handwriting-simulation/overlay \
-H "Content-Type: application/json" \
-d '{
  "buyer_rfq_number":"TEST-V8-PEN-FLOW",
  "page_size":"A4",
  "style":{
    "use_line_ink":true,
    "line_ink_job_id":"REAL-HANDWRITING",
    "use_pen_flow_v8":true,
    "pen_pressure_variation":0.10,
    "pen_edge_softness":0.25,
    "pen_ink_texture":0.06,
    "line_ink_max_height":55,
    "fallback_to_font":true
  },
  "fields":[
    {"page":1,"x":120,"y":720,"line_index":1,"scale":0.95},
    {"page":1,"x":120,"y":650,"line_index":2,"scale":1.10}
  ]
}'
```

Open:

```bash
open runtime/handwriting_simulation/outputs/TEST-V8-PEN-FLOW__handwriting_overlay.pdf
```
