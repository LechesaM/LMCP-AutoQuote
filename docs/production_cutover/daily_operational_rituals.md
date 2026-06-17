# Daily Operational Rituals

These morning reviews are mandatory for supervised-live operation.

AO tooling is operationally critical and must be used daily:

- stabilization pages
- operational health
- observability
- governance dashboards
- workload balancing
- fatigue monitoring
- runtime resilience panels

## Daily Runtime Review

Review these areas every morning:

| Area | What to check |
| --- | --- |
| runtime alerts | unresolved alerts |
| queue lag | overdue reviews |
| stale evidence | evidence age |
| source failures | dead parsers and endpoints |
| anomalies | unusual runtime patterns |
| degraded states | fallback usage |
| SLA warnings | uptime degradation |

## Daily Governance Review

Review these areas every morning:

| Area | Requirement |
| --- | --- |
| proof capture | enforced |
| `review_ready` | enforced |
| operator attribution | complete |
| audit continuity | intact |
| escalations | reasonable |
| stale reviews | minimized |

## Operating Rule

- Escalate unresolved critical issues before login continues.
- Do not normalize degraded state.
- Do not bypass `review_ready` or proof capture.
- Do not attempt autonomous remediation.
- Use AO tooling before opening operator work queues.

## Daily Supervised Production Ritual

Run the supervised production ritual once per day to keep harvest, pricing, submission retry, proof enrichment, and reconciliation moving as one controlled chain:

```bash
python3 scripts/daily_supervised_production_ritual.py --max-total 10 --max-submissions 3 --limit 3
```

- Leave `--enable-submit` off unless an operator is intentionally authorizing the submission path for that run.
- Use `--enable-submit --confirm-submit` only when supervised submissions are explicitly approved.
- Review the generated report in `runtime/manual_production/daily_supervised_production_ritual.json` after each run.

## Scheduled Operator Job

The daily ritual is also registered as a Celery beat task:

- task: `app.tasks.daily_supervised_production_ritual_tasks.run_daily_supervised_production_ritual_task`
- queue: `operations_queue`
- default cadence: once every 24 hours

The scheduled task reads its runtime limits from these optional environment variables:

- `DAILY_SUPERVISED_PRODUCTION_RITUAL_LIMIT`
- `DAILY_SUPERVISED_PRODUCTION_RITUAL_MAX_TOTAL`
- `DAILY_SUPERVISED_PRODUCTION_RITUAL_MAX_SUBMISSIONS`
- `DAILY_SUPERVISED_PRODUCTION_RITUAL_MIN_SUBMITTED`
- `DAILY_SUPERVISED_PRODUCTION_RITUAL_ENABLE_SUBMIT`
- `DAILY_SUPERVISED_PRODUCTION_RITUAL_CONFIRM_SUBMIT`
- `DAILY_SUPERVISED_PRODUCTION_RITUAL_INTERVAL_HOURS`
