# LMCP V50.8.2 - eTenders Document URL Reconstruction

## Copy files

```bash
cd /Users/Shared/LMCP-AutoQuote-Server

cp lmcp_v50_8_2_etenders_document_url_reconstruction/app/services/etenders_document_url_reconstruction_v50_8_2_service.py app/services/
cp lmcp_v50_8_2_etenders_document_url_reconstruction/app/api/etenders_document_url_reconstruction_v50_8_2_api.py app/api/
```

## Add router to app/main.py

Inside `OPTIONAL_ROUTERS`, add this below V50.8.1:

```python
("etenders_document_url_reconstruction_v50_8_2_router", "app.api.etenders_document_url_reconstruction_v50_8_2_api", "router"),
```

## Compile

```bash
python3 -m py_compile app/services/etenders_document_url_reconstruction_v50_8_2_service.py
python3 -m py_compile app/api/etenders_document_url_reconstruction_v50_8_2_api.py
python3 -m py_compile app/main.py
```

## Restart

```bash
docker compose restart api
sleep 8
```

## Test status

```bash
curl http://localhost:8000/v50-8-2-etenders-docurl/status
```

## Test reconstruction

```bash
curl -X POST http://localhost:8000/v50-8-2-etenders-docurl/reconstruct \
  -H "Content-Type: application/json" \
  -d '{
    "title":"RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK (INCLUDING PRINTED COPIES) FOR THE JDA 25TH ANNIVERSARY 08/05/2026 in 6 days",
    "source_url":"https://www.etenders.gov.za/Home/opportunities"
  }'
```

## Interpret results

Good result:
```json
"recommended_action": "promote_verified_reconstructed_document",
"safe_to_download": true
```

If it returns:
```json
"candidate_urls_reconstructed_but_not_verified"
```

Then send back the `probed_candidates` section. That tells us the correct endpoint pattern still differs from the tested known patterns.
