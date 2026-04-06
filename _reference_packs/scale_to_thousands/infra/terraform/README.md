# Terraform Add-ons (Scale-to-Thousands)

These files are designed to be added to your existing `infra/terraform` stack.

## Files
- `sqs_stage_queues.tf` — SQS queues per pipeline stage (ingest, extract, pricing, pack, send)
- `ecs_worker_pools.tf` — Multiple ECS worker services, each pinned to a queue via env `CELERY_QUEUES`
- `rds_read_replica.tf` — Read replica for reporting
- `dr_primitives.tf` — S3 cross-region replication + RDS snapshot copy scaffolding
- `bluegreen_codedeploy_blueprint.tf` — CodeDeploy app + deployment group skeleton for ECS blue/green

## Apply strategy
Start with:
1) `sqs_stage_queues.tf`
2) `ecs_worker_pools.tf`
3) `rds_read_replica.tf`

Then add DR + blue/green once stable.

## Required variables you may add
- `dr_region` (e.g. eu-west-1)
- `enable_dr` (bool)
- `enable_bluegreen` (bool)
- `worker_max_*` caps (per stage)
