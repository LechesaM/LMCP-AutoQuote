# LMCP V47.5 Guarded Final Submission Automation

V47.5 will only attempt final submission when:

```json
"dry_run": false
"execute_final_submit": true
"confirmation_phrase": "I CONFIRM FINAL SUBMISSION"
```

It does not bypass CAPTCHA and does not submit silently.

## Install

```bash
cd /Users/Shared/LMCP-AutoQuote-Server
unzip ~/Downloads/lmcp_v47_5_guarded_final_submission.zip -d .

cp lmcp_v47_5_guarded_final_submission/app/services/final_submission_v47_5_service.py app/services/final_submission_v47_5_service.py
cp lmcp_v47_5_guarded_final_submission/app/api/final_submission_v47_5_api.py app/api/final_submission_v47_5_api.py
```

Add to `OPTIONAL_ROUTERS` in `app/main.py`:

```python
("final_submission_v47_5_router", "app.api.final_submission_v47_5_api", "router"),
```

Restart:

```bash
docker compose restart api
sleep 8
curl http://localhost:8000/v47-final-submit/status
```
