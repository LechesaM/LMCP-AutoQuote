# Auth RBAC Policy

## Roles

- `admin`
- `supervisor`
- `operator`
- `governance`
- `read_only`

## Permissions

- `view_dashboard`
- `view_rfqs`
- `view_operator_queue`
- `assign_operator`
- `mark_reviewed`
- `escalate_review`
- `archive_rfq`
- `acknowledge_alert`
- `view_audit`
- `view_governance`
- `manage_sources`
- `manage_users`

## Denied autonomous permissions

- `autonomous_submit`
- `auto_approve`
- `bypass_review_ready`
- `bypass_proof_capture`

## Operator action permissions

- Assign: `assign_operator`
- Reviewed: `mark_reviewed`
- Escalate: `escalate_review`
- Archive: `archive_rfq`
- Acknowledge alert: `acknowledge_alert`

All actions remain explicit and audited.

