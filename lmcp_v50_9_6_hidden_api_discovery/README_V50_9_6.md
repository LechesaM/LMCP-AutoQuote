# LMCP V50.9.6 - Hidden API Discovery + DownloadSpec Replay

## Step 1: Copy files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp lmcp_v50_9_6_hidden_api_discovery/app/services/etenders_hidden_api_discovery_v50_9_6_service.py app/services/

cp lmcp_v50_9_6_hidden_api_discovery/app/api/etenders_hidden_api_discovery_v50_9_6_api.py app/api/
```

## Step 2: Add router to `app/main.py`

Find:

```python
("etenders_dom_trigger_forced_click_v50_9_5_router", "app.api.etenders_dom_trigger_forced_click_v50_9_5_api", "router"),
```

Add directly underneath:

```python
("etenders_hidden_api_discovery_v50_9_6_router", "app.api.etenders_hidden_api_discovery_v50_9_6_api", "router"),
```

## Step 3: Compile

```bash
python3 -m py_compile app/services/etenders_hidden_api_discovery_v50_9_6_service.py

python3 -m py_compile app/api/etenders_hidden_api_discovery_v50_9_6_api.py

python3 -m py_compile app/main.py
```

## Step 4: Restart

```bash
docker compose restart api
sleep 8
```

## Step 5: Status

```bash
curl http://localhost:8000/v50-9-6-hidden-api-discovery/status
```

## Step 6: Discover hidden API + probe document IDs

Start narrow first:

```bash
curl -X POST http://localhost:8000/v50-9-6-hidden-api-discovery/discover \
  -H "Content-Type: application/json" \
  -d '{
    "tender_id":155559,
    "supportDocumentID":"e7904db8-9865-48c3-95ae-b28e417c92bc",
    "start_document_id":1,
    "end_document_id":120,
    "save_verified":true
  }'
```

If needed, scan higher:

```bash
curl -X POST http://localhost:8000/v50-9-6-hidden-api-discovery/discover \
  -H "Content-Type: application/json" \
  -d '{
    "tender_id":155559,
    "supportDocumentID":"e7904db8-9865-48c3-95ae-b28e417c92bc",
    "start_document_id":121,
    "end_document_id":300,
    "save_verified":true
  }'
```

## Step 7: Replay a known document ID

```bash
curl -X POST http://localhost:8000/v50-9-6-hidden-api-discovery/replay-download \
  -H "Content-Type: application/json" \
  -d '{
    "tender_id":155559,
    "document_id":73
  }'
```
