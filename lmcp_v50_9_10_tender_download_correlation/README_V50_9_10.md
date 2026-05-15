# LMCP V50.9.10 - Intelligent Tender-to-Download Correlation

## Step 1: Copy files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp lmcp_v50_9_10_tender_download_correlation/app/services/etenders_tender_download_correlation_v50_9_10.py app/services/

cp lmcp_v50_9_10_tender_download_correlation/app/api/etenders_tender_download_correlation_v50_9_10_api.py app/api/
```

## Step 2: Add router to `app/main.py`

Find:

```python
("etenders_runtime_download_interceptor_v50_9_9_router", "app.api.etenders_runtime_download_interceptor_v50_9_9_api", "router"),
```

Add underneath:

```python
("etenders_tender_download_correlation_v50_9_10_router", "app.api.etenders_tender_download_correlation_v50_9_10_api", "router"),
```

## Step 3: Compile

```bash
python3 -m py_compile app/services/etenders_tender_download_correlation_v50_9_10.py

python3 -m py_compile app/api/etenders_tender_download_correlation_v50_9_10_api.py

python3 -m py_compile app/main.py
```

## Step 4: Restart

```bash
docker compose restart api
sleep 8
```

## Step 5: Status

```bash
curl http://localhost:8000/v50-9-10-tender-download-correlation/status
```

## Step 6: Correlate latest runtime capture

```bash
curl -X POST http://localhost:8000/v50-9-10-tender-download-correlation/latest \
  -H "Content-Type: application/json" \
  -d '{
    "tender_id":155559,
    "supportDocumentID":"e7904db8-9865-48c3-95ae-b28e417c92bc",
    "tender_no":"JDAMARK/DIGITALBOOK /05/2026",
    "title":"RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK (INCLUDING PRINTED COPIES) FOR THE JDA 25TH ANNIVERSARY",
    "buyer_name":"Johannesburg Development Agency",
    "min_score":45,
    "require_medium_confidence":true
  }'
```
