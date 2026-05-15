# LMCP V50.8.4 - eTenders Multi-Status Enumerator

## Step 1: Copy files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp lmcp_v50_8_4_etenders_status_enumerator/app/services/etenders_status_enumerator_v50_8_4_service.py app/services/
cp lmcp_v50_8_4_etenders_status_enumerator/app/api/etenders_status_enumerator_v50_8_4_api.py app/api/
```

## Step 2: Add router to app/main.py

Inside `OPTIONAL_ROUTERS`, add this below V50.8.3:

```python
("etenders_status_enumerator_v50_8_4_router", "app.api.etenders_status_enumerator_v50_8_4_api", "router"),
```

## Step 3: Compile

```bash
python3 -m py_compile app/services/etenders_status_enumerator_v50_8_4_service.py
python3 -m py_compile app/api/etenders_status_enumerator_v50_8_4_api.py
python3 -m py_compile app/main.py
```

## Step 4: Restart

```bash
docker compose restart api
sleep 8
```

## Step 5: Test status

```bash
curl http://localhost:8000/v50-8-4-etenders-status/status
```

## Step 6: Test enumeration

```bash
curl -X POST http://localhost:8000/v50-8-4-etenders-status/enumerate \
  -H "Content-Type: application/json" \
  -d '{
    "title":"RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK (INCLUDING PRINTED COPIES) FOR THE JDA 25TH ANNIVERSARY",
    "length":50,
    "starts":[0,50,100,150,200]
  }'
```

## Good result

```json
"recommended_action": "matched_rows_found"
```

If it finds rows, send back `matched_rows`.
