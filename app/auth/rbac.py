from __future__ import annotations

from .auth_models import AuthPermission


READ_ONLY_PERMISSIONS = (
    AuthPermission.view_rfqs.value,
    AuthPermission.view_operator_queue.value,
    AuthPermission.view_operator_review.value,
    AuthPermission.view_audit.value,
    AuthPermission.view_governance.value,
    AuthPermission.view_supplier_quote_intelligence.value,
)

OPERATOR_PERMISSIONS = READ_ONLY_PERMISSIONS

SUPERVISOR_PERMISSIONS = (
    *OPERATOR_PERMISSIONS,
    AuthPermission.run_operator_assign_supplier.value,
    AuthPermission.run_operator_mark_reviewed.value,
    AuthPermission.run_operator_request_clarification.value,
    AuthPermission.run_operator_reject_rfq.value,
    AuthPermission.run_operator_escalate_rfq.value,
    AuthPermission.run_operator_acknowledge_alert.value,
    AuthPermission.execute_submission.value,
    AuthPermission.approve_submission.value,
    AuthPermission.verify_submission.value,
    AuthPermission.reconcile_submission.value,
    AuthPermission.export_audit.value,
    AuthPermission.run_submission_package_generate.value,
    AuthPermission.run_supplier_quote_intelligence.value,
    AuthPermission.run_supplier_quote_auto_ingest.value,
    AuthPermission.run_supplier_quote_ingestion.value,
)

ADMIN_PERMISSIONS = (*SUPERVISOR_PERMISSIONS, AuthPermission.manage_users.value)

ROLE_PERMISSIONS = {
    "read_only": READ_ONLY_PERMISSIONS,
    "operator": OPERATOR_PERMISSIONS,
    "supervisor": SUPERVISOR_PERMISSIONS,
    "admin": ADMIN_PERMISSIONS,
}
