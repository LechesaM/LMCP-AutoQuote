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
