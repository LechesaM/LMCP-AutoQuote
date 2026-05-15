
# LMCP V47.7 Deep Verification + Audit Trail Engine

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v47_7_deep_verification_audit.zip -d .

cp lmcp_v47_7_deep_verification_audit/app/services/deep_verification_v47_7_service.py app/services/deep_verification_v47_7_service.py
cp lmcp_v47_7_deep_verification_audit/app/api/deep_verification_v47_7_api.py app/api/deep_verification_v47_7_api.py
```

Add to `OPTIONAL_ROUTERS`:

```python
("deep_verification_v47_7_router", "app.api.deep_verification_v47_7_api", "router"),
```

Restart:

```bash
docker compose restart api
sleep 8
curl http://localhost:8000/v47-deep-verification/status
```
