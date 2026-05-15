# LMCP V50.9.3 - Browser Session Download Interceptor

## What this does

This engine attaches to a live Chrome session and captures the real eTenders document download request.

It is the correct next step after V50.9.2, because direct endpoint guessing returned 404.

## Step 1: Copy files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp lmcp_v50_9_3_browser_download_interceptor/app/services/etenders_browser_download_interceptor_v50_9_3_service.py app/services/

cp lmcp_v50_9_3_browser_download_interceptor/app/api/etenders_browser_download_interceptor_v50_9_3_api.py app/api/
```

## Step 2: Add router to app/main.py

Find:

```python
("etenders_support_document_download_v50_9_2_router", "app.api.etenders_support_document_download_v50_9_2_api", "router"),
```

Add directly below:

```python
("etenders_browser_download_interceptor_v50_9_3_router", "app.api.etenders_browser_download_interceptor_v50_9_3_api", "router"),
```

## Step 3: Compile

```bash
python3 -m py_compile app/services/etenders_browser_download_interceptor_v50_9_3_service.py

python3 -m py_compile app/api/etenders_browser_download_interceptor_v50_9_3_api.py

python3 -m py_compile app/main.py
```

## Step 4: Restart API

```bash
docker compose restart api
sleep 8
```

## Step 5: Test status

```bash
curl http://localhost:8000/v50-9-3-browser-download-interceptor/status
```

## Step 6: Start Chrome with remote debugging on Mac

Close Chrome fully first, then run:

```bash
open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir="/tmp/lmcp-chrome-cdp"
```

In that Chrome window, open:

```text
https://www.etenders.gov.za/Home/opportunities
```

## Step 7: Run capture

```bash
curl -X POST http://localhost:8000/v50-9-3-browser-download-interceptor/capture \
  -H "Content-Type: application/json" \
  -d '{
    "tender_id":155559,
    "supportDocumentID":"e7904db8-9865-48c3-95ae-b28e417c92bc",
    "filename":"RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK +INCLUDING PRINTED COPIES.pdf",
    "tender_url":"https://www.etenders.gov.za/Home/TenderDetails?id=155559",
    "cdp_url":"http://host.docker.internal:9222",
    "wait_seconds":30,
    "auto_click":true
  }'
```

If it does not auto-click the document, run the same command again and manually click the document/download link in Chrome while the command is waiting.

## Output files

Capture logs and screenshots will be saved under:

```text
runtime/playwright/downloads/
```
