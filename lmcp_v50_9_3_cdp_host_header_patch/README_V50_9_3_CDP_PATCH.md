# LMCP V50.9.3 CDP Host Header Patch

This replaces:

```text
app/services/etenders_browser_download_interceptor_v50_9_3_service.py
app/api/etenders_browser_download_interceptor_v50_9_3_api.py
```

## Fix

Docker can reach Chrome CDP only with:

```text
Host: localhost:9222
```

Chrome returns:

```text
ws://localhost:9222/devtools/browser/...
```

The patched service rewrites it to:

```text
ws://host.docker.internal:9222/devtools/browser/...
```

## Step 1: Backup current files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp app/services/etenders_browser_download_interceptor_v50_9_3_service.py app/services/etenders_browser_download_interceptor_v50_9_3_service.py.backup

cp app/api/etenders_browser_download_interceptor_v50_9_3_api.py app/api/etenders_browser_download_interceptor_v50_9_3_api.py.backup
```

## Step 2: Copy patched files

```bash
cp lmcp_v50_9_3_cdp_host_header_patch/app/services/etenders_browser_download_interceptor_v50_9_3_service.py app/services/

cp lmcp_v50_9_3_cdp_host_header_patch/app/api/etenders_browser_download_interceptor_v50_9_3_api.py app/api/
```

## Step 3: Compile

```bash
python3 -m py_compile app/services/etenders_browser_download_interceptor_v50_9_3_service.py

python3 -m py_compile app/api/etenders_browser_download_interceptor_v50_9_3_api.py

python3 -m py_compile app/main.py
```

## Step 4: Restart

```bash
docker compose restart api
sleep 8
```

## Step 5: Test status

```bash
curl http://localhost:8000/v50-9-3-browser-download-interceptor/status
```

Expected:

```text
V50.9.3_ETENDERS_BROWSER_DOWNLOAD_INTERCEPTOR_CDP_PATCH
```

## Step 6: Capture

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
