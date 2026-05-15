# LMCP V50.8.1 - eTenders Ajax/DataTables Resolver

## Copy files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp lmcp_v50_8_1_etenders_ajax_datatables_resolver/app/services/etenders_ajax_datatables_resolver_v50_8_1_service.py app/services/
cp lmcp_v50_8_1_etenders_ajax_datatables_resolver/app/api/etenders_ajax_datatables_resolver_v50_8_1_api.py app/api/
```

## Add router to app/main.py

In `OPTIONAL_ROUTERS`, add:

```python
("etenders_ajax_datatables_resolver_v50_8_1_router", "app.api.etenders_ajax_datatables_resolver_v50_8_1_api", "router"),
```

Good place: below the V50.8 router.

## Compile

```bash
python3 -m py_compile app/services/etenders_ajax_datatables_resolver_v50_8_1_service.py
python3 -m py_compile app/api/etenders_ajax_datatables_resolver_v50_8_1_api.py
python3 -m py_compile app/main.py
```

## Restart

```bash
docker compose restart api
sleep 8
```

## Test status

```bash
curl http://localhost:8000/v50-8-1-etenders-ajax/status
```

## Test resolver

```bash
curl -X POST http://localhost:8000/v50-8-1-etenders-ajax/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "title":"RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK (INCLUDING PRINTED COPIES) FOR THE JDA 25TH ANNIVERSARY 08/05/2026 in 6 days",
    "source_url":"https://www.etenders.gov.za/Home/opportunities"
  }'
```

## Wire into tender_harvester.py after V50.8

Import:

```python
try:
    from app.services.etenders_ajax_datatables_resolver_v50_8_1_service import resolve_etenders_ajax_datatables
except Exception:
    resolve_etenders_ajax_datatables = None
```

After V50.8 fails or returns no matching row:

```python
if resolve_etenders_ajax_datatables is not None:
    v50_8_1 = resolve_etenders_ajax_datatables(item)
    item["v50_8_1_ajax_resolution_result"] = v50_8_1
    item["v50_8_1_recommended_action"] = v50_8_1.get("recommended_action")

    docs = v50_8_1.get("recommended_document_links") or []
    details = v50_8_1.get("recommended_detail_links") or []

    if docs:
        item["document_url"] = docs[0]["url"]
        item["detail_url"] = docs[0]["url"]
        item["v50_8_1_verified_document_url"] = docs[0]["url"]
        item["skip_document_acquisition_until_detail_verified"] = False

    elif details:
        item["detail_url"] = details[0]["url"]
        item["v50_8_1_verified_detail_url"] = details[0]["url"]
        item["skip_document_acquisition_until_detail_verified"] = False
```
