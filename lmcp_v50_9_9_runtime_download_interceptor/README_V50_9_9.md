# LMCP V50.9.9 - Runtime Browser Download Interceptor

## Step 1: Copy files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp lmcp_v50_9_9_runtime_download_interceptor/app/services/etenders_runtime_download_interceptor_v50_9_9.py app/services/

cp lmcp_v50_9_9_runtime_download_interceptor/app/api/etenders_runtime_download_interceptor_v50_9_9_api.py app/api/
```

## Step 2: Add router to `app/main.py`

Find:

```python
("etenders_download_replay_reconstruction_v50_9_8_router", "app.api.etenders_download_replay_reconstruction_v50_9_8_api", "router"),
```

Add underneath:

```python
("etenders_runtime_download_interceptor_v50_9_9_router", "app.api.etenders_runtime_download_interceptor_v50_9_9_api", "router"),
```

## Step 3: Compile

```bash
python3 -m py_compile app/services/etenders_runtime_download_interceptor_v50_9_9.py

python3 -m py_compile app/api/etenders_runtime_download_interceptor_v50_9_9_api.py

python3 -m py_compile app/main.py
```

## Step 4: Restart

```bash
docker compose restart api
sleep 8
```

## Step 5: Status

```bash
curl http://localhost:8000/v50-9-9-runtime-download-interceptor/status
```

## Step 6: Capture runtime browser activity

Make sure Chrome CDP is running:

```bash
open -na "Google Chrome" --args --remote-debugging-address=0.0.0.0 --remote-debugging-port=9222 --user-data-dir="/tmp/lmcp-chrome-cdp"
```

Then run:

```bash
curl -X POST http://localhost:8000/v50-9-9-runtime-download-interceptor/capture \
  -H "Content-Type: application/json" \
  -d '{
    "tender_id":155559,
    "supportDocumentID":"e7904db8-9865-48c3-95ae-b28e417c92bc",
    "tender_no":"JDAMARK/DIGITALBOOK /05/2026",
    "title":"RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK (INCLUDING PRINTED COPIES) FOR THE JDA 25TH ANNIVERSARY",
    "search_text":"DIGITAL BOOK",
    "tender_url":"https://www.etenders.gov.za/Home/opportunities",
    "cdp_url":"http://host.docker.internal:9222",
    "wait_seconds":90,
    "auto_click":true
  }'
```

If it returns `needs_manual_click`, run it again with `wait_seconds:120`, then manually click the document link while capture is running.
