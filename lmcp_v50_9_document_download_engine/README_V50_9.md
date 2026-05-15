# LMCP V50.9 - eTenders Document Auto-Download Engine

## Step 1: Copy files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp lmcp_v50_9_document_download_engine/app/services/etenders_document_download_v50_9_service.py app/services/

cp lmcp_v50_9_document_download_engine/app/api/etenders_document_download_v50_9_api.py app/api/
```

## Step 2: Add router to `app/main.py`

Open:

```bash
nano app/main.py
```

Find the V50.8.5 router line:

```python
("etenders_local_filter_v50_8_5_router", "app.api.etenders_local_filter_v50_8_5_api", "router"),
```

Add directly below it:

```python
("etenders_document_download_v50_9_router", "app.api.etenders_document_download_v50_9_api", "router"),
```

Save:

```text
Control + O
Enter
Control + X
```

## Step 3: Compile

```bash
python3 -m py_compile app/services/etenders_document_download_v50_9_service.py

python3 -m py_compile app/api/etenders_document_download_v50_9_api.py

python3 -m py_compile app/main.py
```

## Step 4: Restart

```bash
docker compose restart api
sleep 8
```

## Step 5: Test status

```bash
curl http://localhost:8000/v50-9-document-download/status
```

## Step 6: Test download

```bash
curl -X POST http://localhost:8000/v50-9-document-download/download \
  -H "Content-Type: application/json" \
  -d '{
    "tender_id":155559,
    "document_guid":"e7904db8-9865-48c3-95ae-b28e417c92bc",
    "filename":"RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK +INCLUDING PRINTED COPIES.pdf"
  }'
```
