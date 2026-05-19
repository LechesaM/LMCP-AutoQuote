# Health Monitoring SOP

## Endpoints

- `/health`
- `/health/system`
- `/health/workflows`
- `/health/operational-report`

## Meaning of Each View

- `/health` reports overall application status and runtime context
- `/health/system` reports component-level health
- `/health/workflows` reports workflow queue and stage health
- `/health/operational-report` provides a combined operational summary

## Warning Interpretation

- `healthy` means operations can continue normally
- `degraded` means operations may continue with caution and operator oversight
- `unhealthy` or equivalent severe status means pause and investigate

## When to Pause Operations

- DB persistence failures are sustained
- Workflow transitions fail repeatedly
- Audit output is missing or corrupt
- Required runtime directories are missing

## Escalation Rules

- Escalate unresolved health issues to the shift lead
- Refuse new RFQs if the operational state cannot be trusted

