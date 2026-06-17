from __future__ import annotations

from enum import Enum


class AuthPermission(str, Enum):
    manage_users = "manage_users"
    view_rfqs = "view_rfqs"
    view_operator_queue = "view_operator_queue"
    view_operator_review = "view_operator_review"
    view_audit = "view_audit"
    view_governance = "view_governance"
    view_supplier_quote_intelligence = "view_supplier_quote_intelligence"
    run_supplier_quote_intelligence = "run_supplier_quote_intelligence"
    run_supplier_quote_auto_ingest = "run_supplier_quote_auto_ingest"
    run_supplier_quote_ingestion = "run_supplier_quote_ingestion"
    run_operator_assign_supplier = "run_operator_assign_supplier"
    run_operator_mark_reviewed = "run_operator_mark_reviewed"
    run_operator_request_clarification = "run_operator_request_clarification"
    run_operator_reject_rfq = "run_operator_reject_rfq"
    run_operator_escalate_rfq = "run_operator_escalate_rfq"
    run_operator_acknowledge_alert = "run_operator_acknowledge_alert"
    execute_submission = "execute_submission"
    approve_submission = "approve_submission"
    verify_submission = "verify_submission"
    reconcile_submission = "reconcile_submission"
    export_audit = "export_audit"
    run_submission_package_generate = "run_submission_package_generate"
