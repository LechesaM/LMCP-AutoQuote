# LMCP V50.9.2 - SupportDocument Direct Download Probe

## Step 1: Copy files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp lmcp_v50_9_2_support_document_download/app/services/etenders_support_document_download_v50_9_2_service.py app/services/

cp lmcp_v50_9_2_support_document_download/app/api/etenders_support_document_download_v50_9_2_api.py app/api/
```

## Step 2: Add router to app/main.py

Find:

```python
("etenders_tenderdetails_json_v50_9_1_router", "app.api.etenders_tenderdetails_json_v50_9_1_api", "router"),
```

Add directly below:

```python
("etenders_support_document_download_v50_9_2_router", "app.api.etenders_support_document_download_v50_9_2_api", "router"),
```

## Step 3: Compile

```bash
python3 -m py_compile app/services/etenders_support_document_download_v50_9_2_service.py
python3 -m py_compile app/api/etenders_support_document_download_v50_9_2_api.py
python3 -m py_compile app/main.py
```

## Step 4: Restart

```bash
docker compose restart api
sleep 8
```

## Step 5: Test status

```bash
curl http://localhost:8000/v50-9-2-support-document-download/status
```

## Step 6: Probe

```bash
curl -X POST http://localhost:8000/v50-9-2-support-document-download/probe \
  -H "Content-Type: application/json" \
  -d '{
    "tender_id":155559,
    "supportDocumentID":"e7904db8-9865-48c3-95ae-b28e417c92bc",
    "filename":"RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK +INCLUDING PRINTED COPIES.pdf",
    "max_attempts":160
  }'
```

## Step 7: Download

```bash
curl -X POST http://localhost:8000/v50-9-2-support-document-download/download \
  -H "Content-Type: application/json" \
  -d '{
    "tender_id":155559,
    "supportDocumentID":"e7904db8-9865-48c3-95ae-b28e417c92bc",
    "filename":"RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK +INCLUDING PRINTED COPIES.pdf",
    "max_attempts":220
  }'
```
