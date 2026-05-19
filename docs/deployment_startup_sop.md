# Deployment Startup SOP

## Startup Checklist

- Confirm the intended branch and commit are deployed.
- Confirm runtime paths exist.
- Confirm environment validation passes.
- Confirm startup validation passes or approved degraded mode is enabled.
- Confirm persistence and monitoring are available.
- Confirm dashboard and workflow services are available.

## Validation Checks

- Router registry integrity
- SQLite availability
- JSONL log writability
- Workflow engine availability
- Monitoring availability
- Dashboard availability

## Degraded Startup

- Degraded startup is only acceptable when already permitted by governance.
- Record the reason for degraded startup.
- Do not use degraded startup to bypass manual-production controls.

## Operator Rule

If startup validation is unhealthy and degraded startup is not explicitly allowed, stop and escalate instead of forcing deployment.

