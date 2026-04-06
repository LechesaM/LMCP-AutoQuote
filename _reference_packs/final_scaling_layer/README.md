# AutoQuote Tender Desk — Final Scaling Layer Pack

Adds:
1) Fully expanded ECS worker pools for ALL pipeline stages (ingest/extract/pricing/pack/send)
2) EventBridge schedules (polling + maintenance jobs)
3) Athena/Glue audit analytics scaffolding (query evidence packs + send events)

Drop-in Terraform files go into your existing `infra/terraform/` folder.

Notes:
- Queueing model: Celery queues named ingest/extract/pricing/pack/send.
- Metrics: publish `QueueDepthPerWorker` with Dimension `QueueName` per queue.
- For Athena: we assume your app writes `send_events` export snapshots to S3 as JSON Lines or Parquet.
