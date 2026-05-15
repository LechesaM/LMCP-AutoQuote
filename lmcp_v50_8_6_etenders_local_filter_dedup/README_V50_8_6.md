# LMCP V50.8.6 - eTenders Row Deduplication Patch

This is a corrected full replacement for:

```bash
app/services/etenders_local_filter_v50_8_5_service.py
app/api/etenders_local_filter_v50_8_5_api.py
```

It keeps the same route:

```text
/v50-8-5-etenders-local-filter
```

but the service version will report:

```text
V50.8.6_ETENDERS_LOCAL_STRUCTURED_FILTER_DEDUP
```

## Step 1: Backup current files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp app/services/etenders_local_filter_v50_8_5_service.py app/services/etenders_local_filter_v50_8_5_service.py.backup_v50_8_5

cp app/api/etenders_local_filter_v50_8_5_api.py app/api/etenders_local_filter_v50_8_5_api.py.backup_v50_8_5
```

## Step 2: Copy corrected files

```bash
cp lmcp_v50_8_6_etenders_local_filter_dedup/app/services/etenders_local_filter_v50_8_5_service.py app/services/

cp lmcp_v50_8_6_etenders_local_filter_dedup/app/api/etenders_local_filter_v50_8_5_api.py app/api/
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

Expected:

```json
"service_version":"V50.8.6_ETENDERS_LOCAL_STRUCTURED_FILTER_DEDUP"
```

## Step 6: Test filter

```bash
curl -X POST http://localhost:8000/v50-8-5-etenders-local-filter/filter \
  -H "Content-Type: application/json" \
  -d '{
    "title":"DIGITAL BOOK JDA",
    "statuses":["1","2"],
    "starts":[0,100,200,300,400,500,600,700,800,900],
    "length":100,
    "min_match_score":0.15,
    "markers":["DIGITAL","BOOK","JDA","ANNIVERSARY"]
  }'
```

Check these new fields:

```json
"raw_row_count_before_dedup"
"page_deduped_row_count"
"duplicate_row_count_removed"
"unique_row_count"
"matched_row_count"
```
