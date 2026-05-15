# LMCP V48 Full Autonomous Orchestrator

V48 chains the working system:

V45 pack -> V47 portal pack -> V47.1 autofill -> V47.4 upload -> V47.5 submit -> V47.6 verify -> V47.7 audit

It is policy-guarded:
- disabled by default
- upload disabled by default
- final submit disabled unless mode is controlled/production and explicit policy allows it

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v48_full_autonomous_orchestrator.zip -d .

cp lmcp_v48_full_autonomous_orchestrator/app/services/full_autonomous_v48_service.py app/services/full_autonomous_v48_service.py
cp lmcp_v48_full_autonomous_orchestrator/app/api/full_autonomous_v48_api.py app/api/full_autonomous_v48_api.py
```

Add to `OPTIONAL_ROUTERS` in `app/main.py`:

```python
("full_autonomous_v48_router", "app.api.full_autonomous_v48_api", "router"),
```

Restart:

```bash
docker compose restart api
sleep 8
curl http://localhost:8000/v48-autonomous/status
```

## Enable safe mode

```bash
curl -X POST http://localhost:8000/v48-autonomous/policy \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "mode": "safe",
    "allow_portal_upload": false,
    "allow_portal_final_submit": false
  }'
```

## Enable controlled upload only

```bash
curl -X POST http://localhost:8000/v48-autonomous/policy \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "mode": "controlled",
    "allow_portal_upload": true,
    "allow_portal_final_submit": false
  }'
```

## Enable controlled final submit

```bash
curl -X POST http://localhost:8000/v48-autonomous/policy \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "mode": "controlled",
    "allow_portal_upload": true,
    "allow_portal_final_submit": true
  }'
```
