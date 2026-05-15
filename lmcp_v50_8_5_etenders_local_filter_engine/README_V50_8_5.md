# LMCP V50.8.5 - eTenders Local Structured Filter Engine

## Step 1: Copy files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp lmcp_v50_8_5_etenders_local_filter_engine/app/services/etenders_local_filter_v50_8_5_service.py app/services/
cp lmcp_v50_8_5_etenders_local_filter_engine/app/api/etenders_local_filter_v50_8_5_api.py app/api/
```

## Step 2: Add router to app/main.py

Inside `OPTIONAL_ROUTERS`, add below V50.8.4:

```python
("etenders_local_filter_v50_8_5_router", "app.api.etenders_local_filter_v50_8_5_api", "router"),
```

## Step 3: Compile

```bash
python3 -m py_compile app/services/etenders_local_filter_v50_8_5_service.py
python3 -m py_compile app/api/etenders_local_filter_v50_8_5_api.py
python3 -m py_compile app/main.py
```

## Step 4: Restart

```bash
docker compose restart api
sleep 8
```

## Step 5: Test status

```bash
curl http://localhost:8000/v50-8-5-etenders-local-filter/status
```

## Step 6: Test local filtering

```bash
curl -X POST http://localhost:8000/v50-8-5-etenders-local-filter/filter \
  -H "Content-Type: application/json" \
  -d '{
    "title":"RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK (INCLUDING PRINTED COPIES) FOR THE JDA 25TH ANNIVERSARY",
    "statuses":["1","2"],
    "starts":[0,50,100,150,200,250,300,350,400,450,500],
    "length":50,
    "min_match_score":0.35,
    "markers":["JDAMARK/DIGITALBOOK","DIGITAL BOOK","JDA 25TH ANNIVERSARY"]
  }'
```

## Good result

```json
"recommended_action":"matched_local_rows_found"
```

Then send back:
- `matched_row_count`
- first `matched_rows[0]`
