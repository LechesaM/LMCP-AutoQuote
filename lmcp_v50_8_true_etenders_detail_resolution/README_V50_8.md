# LMCP V50.8 - True eTenders Detail Resolution

## What this adds

V50.8 adds Playwright-assisted row-level detail resolution for eTenders.

It tries to:
- open eTenders listing/source page,
- inspect rows,
- match a row against the harvested RFQ title,
- extract links only from matched rows,
- promote a document only when the row match is strong.

This complements V50.7. V50.7 blocks weak generic links. V50.8 attempts to find the correct row-local link.

---

## Copy files

From project root:

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp lmcp_v50_8_true_etenders_detail_resolution/app/services/true_etenders_detail_resolution_v50_8_service.py app/services/
cp lmcp_v50_8_true_etenders_detail_resolution/app/api/true_etenders_detail_resolution_v50_8_api.py app/api/
```

---

## Add router to app/main.py

Add this tuple to `OPTIONAL_ROUTERS`:

```python
("true_etenders_detail_resolution_v50_8_router", "app.api.true_etenders_detail_resolution_v50_8_api", "router"),
```

Good place: directly under the V50.7 router tuples.

---

## Compile

```bash
python3 -m py_compile app/services/true_etenders_detail_resolution_v50_8_service.py
python3 -m py_compile app/api/true_etenders_detail_resolution_v50_8_api.py
python3 -m py_compile app/main.py
```

---

## Restart and test

```bash
docker compose restart api
sleep 8

curl http://localhost:8000/v50-8-etenders-detail/status
```

Expected:

```json
{"status":"ok","service_version":"V50.8_TRUE_ETENDERS_DETAIL_RESOLUTION"}
```

---

## Test resolve

```bash
curl -X POST http://localhost:8000/v50-8-etenders-detail/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "title":"RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK (INCLUDING PRINTED COPIES) FOR THE JDA 25TH ANNIVERSARY 08/05/2026 in 6 days",
    "source_url":"https://www.etenders.gov.za"
  }'
```

---

## Wire into tender_harvester.py

Import:

```python
try:
    from app.services.true_etenders_detail_resolution_v50_8_service import resolve_true_etenders_detail
except Exception:
    resolve_true_etenders_detail = None
```

Then inside the eTenders branch after V50.7 runs:

```python
if resolve_true_etenders_detail is not None and v50_7_nav.get("safe_to_download") is False:
    v50_8 = resolve_true_etenders_detail(item)
    item["v50_8_detail_resolution_result"] = v50_8
    item["v50_8_recommended_action"] = v50_8.get("recommended_action")

    docs = v50_8.get("recommended_document_links") or []
    details = v50_8.get("recommended_detail_links") or []

    if docs:
        item["document_url"] = docs[0]["url"]
        item["detail_url"] = docs[0]["url"]
        item["v50_8_verified_document_url"] = docs[0]["url"]
        item["skip_document_acquisition_until_detail_verified"] = False
    elif details:
        item["detail_url"] = details[0]["url"]
        item["v50_8_verified_detail_url"] = details[0]["url"]
        item["skip_document_acquisition_until_detail_verified"] = False
```
