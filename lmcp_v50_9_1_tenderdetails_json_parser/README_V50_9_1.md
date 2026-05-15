# LMCP V50.9.1 - TenderDetails JSON Parser + Download Bridge

## Step 1: Copy files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp lmcp_v50_9_1_tenderdetails_json_parser/app/services/etenders_tenderdetails_json_v50_9_1_service.py app/services/

cp lmcp_v50_9_1_tenderdetails_json_parser/app/api/etenders_tenderdetails_json_v50_9_1_api.py app/api/
```

## Step 2: Add router to app/main.py

Find:

```python
("etenders_document_download_v50_9_router", "app.api.etenders_document_download_v50_9_api", "router"),
```

Add directly below it:

```python
("etenders_tenderdetails_json_v50_9_1_router", "app.api.etenders_tenderdetails_json_v50_9_1_api", "router"),
```

## Step 3: Compile

```bash
python3 -m py_compile app/services/etenders_tenderdetails_json_v50_9_1_service.py
python3 -m py_compile app/api/etenders_tenderdetails_json_v50_9_1_api.py
python3 -m py_compile app/main.py
```

## Step 4: Restart

```bash
docker compose restart api
sleep 8
```

## Step 5: Test status

```bash
curl http://localhost:8000/v50-9-1-tenderdetails-json/status
```

## Step 6: Inspect details JSON

```bash
curl -X POST http://localhost:8000/v50-9-1-tenderdetails-json/inspect \
  -H "Content-Type: application/json" \
  -d '{"tender_id":155559}'
```

## Step 7: Try download from details JSON

```bash
curl -X POST http://localhost:8000/v50-9-1-tenderdetails-json/download \
  -H "Content-Type: application/json" \
  -d '{
    "tender_id":155559,
    "document_guid":"e7904db8-9865-48c3-95ae-b28e417c92bc",
    "filename":"RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK +INCLUDING PRINTED COPIES.pdf"
  }'
```
