# LMCP V50.8.3 - eTenders Structured JSON Row Parser

## Copy files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp lmcp_v50_8_3_etenders_structured_json_parser/app/services/etenders_structured_json_parser_v50_8_3_service.py app/services/
cp lmcp_v50_8_3_etenders_structured_json_parser/app/api/etenders_structured_json_parser_v50_8_3_api.py app/api/
```

## Add router to app/main.py

Inside `OPTIONAL_ROUTERS`, add below V50.8.2:

```python
("etenders_structured_json_parser_v50_8_3_router", "app.api.etenders_structured_json_parser_v50_8_3_api", "router"),
```

## Compile

```bash
python3 -m py_compile app/services/etenders_structured_json_parser_v50_8_3_service.py
python3 -m py_compile app/api/etenders_structured_json_parser_v50_8_3_api.py
python3 -m py_compile app/main.py
```

## Restart

```bash
docker compose restart api
sleep 8
```

## Test status

```bash
curl http://localhost:8000/v50-8-3-etenders-json/status
```

## Test parser

```bash
curl -X POST http://localhost:8000/v50-8-3-etenders-json/parse \
  -H "Content-Type: application/json" \
  -d '{
    "title":"RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK (INCLUDING PRINTED COPIES) FOR THE JDA 25TH ANNIVERSARY",
    "source_url":"https://www.etenders.gov.za/Home/opportunities"
  }'
```

## Good result

```json
"recommended_action": "promote_verified_structured_document"
```

or:

```json
"recommended_action": "promote_verified_structured_detail"
```

## If not verified

Send back:
- `matched_rows`
- `structured_candidates`
- `response_summaries`

Those fields will show exactly what endpoint and row keys eTenders is returning.
