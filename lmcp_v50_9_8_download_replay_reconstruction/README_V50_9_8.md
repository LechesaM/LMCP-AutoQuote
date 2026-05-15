# LMCP V50.9.8 - Download Replay Reconstruction

## Step 1: Copy files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp lmcp_v50_9_8_download_replay_reconstruction/app/services/etenders_download_replay_reconstruction_v50_9_8_service.py app/services/

cp lmcp_v50_9_8_download_replay_reconstruction/app/api/etenders_download_replay_reconstruction_v50_9_8_api.py app/api/
```

## Step 2: Add router to `app/main.py`

Find:

```python
("etenders_document_mapping_resolver_v50_9_7_router", "app.api.etenders_document_mapping_resolver_v50_9_7_api", "router"),
```

Add underneath:

```python
("etenders_download_replay_reconstruction_v50_9_8_router", "app.api.etenders_download_replay_reconstruction_v50_9_8_api", "router"),
```

## Step 3: Compile

```bash
python3 -m py_compile app/services/etenders_download_replay_reconstruction_v50_9_8_service.py

python3 -m py_compile app/api/etenders_download_replay_reconstruction_v50_9_8_api.py

python3 -m py_compile app/main.py
```

## Step 4: Restart

```bash
docker compose restart api
sleep 8
```

## Step 5: Status

```bash
curl http://localhost:8000/v50-9-8-download-replay-reconstruction/status
```

## Step 6: Reconstruct replay routes

```bash
curl -X POST http://localhost:8000/v50-9-8-download-replay-reconstruction/reconstruct \
  -H "Content-Type: application/json" \
  -d '{
    "tender_id":155559,
    "supportDocumentID":"e7904db8-9865-48c3-95ae-b28e417c92bc",
    "tender_no":"JDAMARK/DIGITALBOOK /05/2026",
    "title":"RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK (INCLUDING PRINTED COPIES) FOR THE JDA 25TH ANNIVERSARY",
    "statuses":["1","Published","Open"],
    "max_pages":12,
    "length":50,
    "max_candidates_to_execute":300,
    "save_downloads":true
  }'
```
