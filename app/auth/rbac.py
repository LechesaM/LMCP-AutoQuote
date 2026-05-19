from __future__ import annotations

from typing import Dict, Iterable, Tuple

from app.auth.auth_models import AuthPermission, AuthRole


ROLE_PERMISSIONS: Dict[str, Tuple[str, ...]] = {
    AuthRole.ADMIN.value: (
        AuthPermission.VIEW_DASHBOARD.value,
        AuthPermission.VIEW_RFQS.value,
        AuthPermission.VIEW_OPERATOR_QUEUE.value,
        AuthPermission.ASSIGN_OPERATOR.value,
        AuthPermission.MARK_REVIEWED.value,
        AuthPermission.ESCALATE_REVIEW.value,
        AuthPermission.ARCHIVE_RFQ.value,
        AuthPermission.ACKNOWLEDGE_ALERT.value,
        AuthPermission.VIEW_AUDIT.value,
        AuthPermission.VIEW_GOVERNANCE.value,
        AuthPermission.MANAGE_SOURCES.value,
        AuthPermission.MANAGE_USERS.value,
    ),
    AuthRole.SUPERVISOR.value: (
        AuthPermission.VIEW_DASHBOARD.value,
        AuthPermission.VIEW_RFQS.value,
        AuthPermission.VIEW_OPERATOR_QUEUE.value,
        AuthPermission.ASSIGN_OPERATOR.value,
        AuthPermission.MARK_REVIEWED.value,
        AuthPermission.ESCALATE_REVIEW.value,
        AuthPermission.ARCHIVE_RFQ.value,
        AuthPermission.ACKNOWLEDGE_ALERT.value,
        AuthPermission.VIEW_AUDIT.value,
        AuthPermission.VIEW_GOVERNANCE.value,
    ),
    AuthRole.OPERATOR.value: (
        AuthPermission.VIEW_DASHBOARD.value,
        AuthPermission.VIEW_RFQS.value,
        AuthPermission.VIEW_OPERATOR_QUEUE.value,
        AuthPermission.MARK_REVIEWED.value,
        AuthPermission.ACKNOWLEDGE_ALERT.value,
    ),
    AuthRole.GOVERNANCE.value: (
        AuthPermission.VIEW_DASHBOARD.value,
        AuthPermission.VIEW_RFQS.value,
        AuthPermission.VIEW_OPERATOR_QUEUE.value,
        AuthPermission.VIEW_AUDIT.value,
        AuthPermission.VIEW_GOVERNANCE.value,
        AuthPermission.ACKNOWLEDGE_ALERT.value,
    ),
    AuthRole.READ_ONLY.value: (
        AuthPermission.VIEW_DASHBOARD.value,
        AuthPermission.VIEW_RFQS.value,
        AuthPermission.VIEW_OPERATOR_QUEUE.value,
        AuthPermission.VIEW_AUDIT.value,
        AuthPermission.VIEW_GOVERNANCE.value,
    ),
}


def permissions_for_role(role: str) -> Tuple[str, ...]:
    return ROLE_PERMISSIONS.get(str(role or "").lower(), tuple())


def role_has_permission(role: str, permission: str) -> bool:
    return str(permission or "").lower() in permissions_for_role(role)


def permissions_for_roles(roles: Iterable[str]) -> Tuple[str, ...]:
    values = []
    for role in roles:
        for permission in permissions_for_role(role):
            if permission not in values:
                values.append(permission)
    return tuple(values)

