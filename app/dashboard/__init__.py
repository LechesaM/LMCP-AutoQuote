from __future__ import annotations


def get_dashboard_summary(*args, **kwargs):
    from .dashboard_service import get_dashboard_summary as _get_dashboard_summary

    return _get_dashboard_summary(*args, **kwargs)


def get_operational_summary(*args, **kwargs):
    from .dashboard_service import get_operational_summary as _get_operational_summary

    return _get_operational_summary(*args, **kwargs)


def get_recent_workflows(*args, **kwargs):
    from .dashboard_service import get_recent_workflows as _get_recent_workflows

    return _get_recent_workflows(*args, **kwargs)


def get_recent_refusals(*args, **kwargs):
    from .dashboard_service import get_recent_refusals as _get_recent_refusals

    return _get_recent_refusals(*args, **kwargs)


def get_recent_approvals(*args, **kwargs):
    from .dashboard_service import get_recent_approvals as _get_recent_approvals

    return _get_recent_approvals(*args, **kwargs)


def get_recent_reviews(*args, **kwargs):
    from .dashboard_service import get_recent_reviews as _get_recent_reviews

    return _get_recent_reviews(*args, **kwargs)


def get_recent_proofs(*args, **kwargs):
    from .dashboard_service import get_recent_proofs as _get_recent_proofs

    return _get_recent_proofs(*args, **kwargs)


def get_dashboard_health(*args, **kwargs):
    from .health_views import get_dashboard_health as _get_dashboard_health

    return _get_dashboard_health(*args, **kwargs)


def get_health_summary(*args, **kwargs):
    from .health_views import get_health_summary as _get_health_summary

    return _get_health_summary(*args, **kwargs)


def acknowledge_warning(*args, **kwargs):
    from .operator_actions_service import acknowledge_warning as _acknowledge_warning

    return _acknowledge_warning(*args, **kwargs)


def add_operator_note(*args, **kwargs):
    from .operator_actions_service import add_operator_note as _add_operator_note

    return _add_operator_note(*args, **kwargs)


def archive_workflow(*args, **kwargs):
    from .operator_actions_service import archive_workflow as _archive_workflow

    return _archive_workflow(*args, **kwargs)


def refuse_workflow(*args, **kwargs):
    from .operator_actions_service import refuse_workflow as _refuse_workflow

    return _refuse_workflow(*args, **kwargs)


def get_operational_report_view(*args, **kwargs):
    from .report_views import get_operational_report_view as _get_operational_report_view

    return _get_operational_report_view(*args, **kwargs)


def get_persistence_report_view(*args, **kwargs):
    from .report_views import get_persistence_report_view as _get_persistence_report_view

    return _get_persistence_report_view(*args, **kwargs)


def get_pricing_report_view(*args, **kwargs):
    from .report_views import get_pricing_report_view as _get_pricing_report_view

    return _get_pricing_report_view(*args, **kwargs)


def get_refusal_report_view(*args, **kwargs):
    from .report_views import get_refusal_report_view as _get_refusal_report_view

    return _get_refusal_report_view(*args, **kwargs)


def get_workflow_report_view(*args, **kwargs):
    from .report_views import get_workflow_report_view as _get_workflow_report_view

    return _get_workflow_report_view(*args, **kwargs)


def get_archived_queue(*args, **kwargs):
    from .workflow_queue_service import get_archived_queue as _get_archived_queue

    return _get_archived_queue(*args, **kwargs)


def get_pending_approval_queue(*args, **kwargs):
    from .workflow_queue_service import get_pending_approval_queue as _get_pending_approval_queue

    return _get_pending_approval_queue(*args, **kwargs)


def get_proof_capture_queue(*args, **kwargs):
    from .workflow_queue_service import get_proof_capture_queue as _get_proof_capture_queue

    return _get_proof_capture_queue(*args, **kwargs)


def get_refused_queue(*args, **kwargs):
    from .workflow_queue_service import get_refused_queue as _get_refused_queue

    return _get_refused_queue(*args, **kwargs)


def get_review_ready_queue(*args, **kwargs):
    from .workflow_queue_service import get_review_ready_queue as _get_review_ready_queue

    return _get_review_ready_queue(*args, **kwargs)

