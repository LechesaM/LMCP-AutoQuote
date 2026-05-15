# LMCP V50.9.7 - Tender Document Mapping Resolver

## Step 1: Copy files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp lmcp_v50_9_7_tender_document_mapping_resolver/app/services/etenders_document_mapping_resolver_v50_9_7_service.py app/services/

cp lmcp_v50_9_7_tender_document_mapping_resolver/app/api/etenders_document_mapping_resolver_v50_9_7_api.py app/api/
```

## Step 2: Add router to `app/main.py`

Find:

```python
("etenders_hidden_api_discovery_v50_9_6_router", "app.api.etenders_hidden_api_discovery_v50_9_6_api", "router"),
```

Add underneath:

```python
("etenders_document_mapping_resolver_v50_9_7_router", "app.api.etenders_document_mapping_resolver_v50_9_7_api", "router"),
```

## Step 3: Compile

```bash
python3 -m py_compile app/services/etenders_document_mapping_resolver_v50_9_7_service.py

python3 -m py_compile app/api/etenders_document_mapping_resolver_v50_9_7_api.py

python3 -m py_compile app/main.py
```

## Step 4: Restart

```bash
docker compose restart api
sleep 8
```

## Step 5: Status

```bash
curl http://localhost:8000/v50-9-7-document-mapping-resolver/status
```

## Step 6: Resolve tender-specific document mapping

```bash
curl -X POST http://localhost:8000/v50-9-7-document-mapping-resolver/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "tender_id":155559,
    "tender_no":"JDAMARK/DIGITALBOOK /05/2026",
    "title":"RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK (INCLUDING PRINTED COPIES) FOR THE JDA 25TH ANNIVERSARY",
    "statuses":["1","2","3","4","5","Published","Open"],
    "max_pages":8,
    "length":50,
    "save_downloads":true
  }'
```
