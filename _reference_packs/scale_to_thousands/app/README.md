# App Changes (Scale-to-Thousands)

## 1) Celery routing: stage queues
Use multiple queues to isolate heavy tasks.
- ingest: polling + dedupe
- extract: document download + parsing + extraction
- pricing: pricing engine
- pack: PDF/ZIP evidence building
- send: gated send + rate limiting

See:
- `celery_routing.py`
- `tasks_pipeline.py`

## 2) Ranking engine
See `ranking_engine.py` and `docs/ranking_engine.md`.
