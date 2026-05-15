# LMCP V50.9.5 - DOM Trigger + Forced Click Injection

## Step 1: Copy files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp lmcp_v50_9_5_dom_trigger_forced_click/app/services/etenders_dom_trigger_forced_click_v50_9_5_service.py app/services/

cp lmcp_v50_9_5_dom_trigger_forced_click/app/api/etenders_dom_trigger_forced_click_v50_9_5_api.py app/api/
```

## Step 2: Add router to app/main.py

Find:

```python
("etenders_dom_modal_autoclick_v50_9_4_router", "app.api.etenders_dom_modal_autoclick_v50_9_4_api", "router"),
```

Add directly below:

```python
("etenders_dom_trigger_forced_click_v50_9_5_router", "app.api.etenders_dom_trigger_forced_click_v50_9_5_api", "router"),
```

## Step 3: Compile

```bash
python3 -m py_compile app/services/etenders_dom_trigger_forced_click_v50_9_5_service.py
python3 -m py_compile app/api/etenders_dom_trigger_forced_click_v50_9_5_api.py
python3 -m py_compile app/main.py
```

## Step 4: Restart

```bash
docker compose restart api
sleep 8
```

## Step 5: Status

```bash
curl http://localhost:8000/v50-9-5-dom-trigger-forced-click/status
```

## Step 6: Capture

```bash
curl -X POST http://localhost:8000/v50-9-5-dom-trigger-forced-click/capture \
  -H "Content-Type: application/json" \
  -d '{
    "tender_id":155559,
    "supportDocumentID":"e7904db8-9865-48c3-95ae-b28e417c92bc",
    "filename":"RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK +INCLUDING PRINTED COPIES.pdf",
    "search_text":"DIGITAL BOOK",
    "tender_url":"https://www.etenders.gov.za/Home/opportunities",
    "cdp_url":"http://host.docker.internal:9222",
    "wait_seconds":60
  }'
```
