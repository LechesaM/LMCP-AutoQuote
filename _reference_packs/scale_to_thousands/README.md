# AutoQuote Tender Desk — Scale-to-Thousands Implementation Pack

This pack extends your production MVP to handle **thousands of RFQs/month** safely.

Contents:
- `infra/terraform/` — Terraform add-ons (SQS stage queues, worker pools, read replica, DR primitives, blue/green notes)
- `db/migrations/` — SQL migrations: multi-tenant (`tenant_id`), indexes, partitioning templates
- `app/` — Celery routing + stage worker commands + ranking engine skeleton
- `docs/` — Ranking engine spec + ops dashboards checklist

## How to use
1) Apply DB migrations in order (see `db/migrations/README.md`).
2) Update your app to use stage queues + routing (see `app/README.md`).
3) Apply Terraform add-ons selectively (see `infra/terraform/README.md`).

> Note: Blue/Green on ECS requires CodeDeploy + IAM + ALB listener rules. We include a robust blueprint and the exact resources you need, but you may tailor to your existing repo/cluster layout.
