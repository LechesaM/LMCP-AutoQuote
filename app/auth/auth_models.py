from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Tuple


class AuthRole(str, Enum):
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    OPERATOR = "operator"
    GOVERNANCE = "governance"
    READ_ONLY = "read_only"


class AuthPermission(str, Enum):
    VIEW_DASHBOARD = "view_dashboard"
    VIEW_RFQS = "view_rfqs"
    VIEW_OPERATOR_QUEUE = "view_operator_queue"
    ASSIGN_OPERATOR = "assign_operator"
    MARK_REVIEWED = "mark_reviewed"
    ESCALATE_REVIEW = "escalate_review"
    ARCHIVE_RFQ = "archive_rfq"
    ACKNOWLEDGE_ALERT = "acknowledge_alert"
    VIEW_AUDIT = "view_audit"
    VIEW_GOVERNANCE = "view_governance"
    MANAGE_SOURCES = "manage_sources"
    MANAGE_USERS = "manage_users"


@dataclass(frozen=True)
class AuthUserRecord:
    user_id: str
    email: str
    display_name: str
    role: str
    password_hash: str
    is_active: bool = True
    created_at: str = ""
    last_login_at: str = ""

    def to_jsonable_dict(self) -> Dict[str, object]:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role,
            "is_active": bool(self.is_active),
            "created_at": self.created_at,
            "last_login_at": self.last_login_at,
        }


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    email: str
    display_name: str
    role: str
    permissions: Tuple[str, ...] = field(default_factory=tuple)
    authenticated: bool = True
    auth_source: str = "jwt"
    token: str = ""
    expires_at: str = ""

    def to_jsonable_dict(self) -> Dict[str, object]:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role,
            "permissions": list(self.permissions),
            "authenticated": bool(self.authenticated),
            "auth_source": self.auth_source,
            "expires_at": self.expires_at,
        }


DEMO_USERS: Tuple[Dict[str, str], ...] = (
    {"user_id": "admin", "email": "admin@lmcp.local", "display_name": "Admin", "role": AuthRole.ADMIN.value, "password": "admin"},
    {"user_id": "supervisor", "email": "supervisor@lmcp.local", "display_name": "Supervisor", "role": AuthRole.SUPERVISOR.value, "password": "supervisor"},
    {"user_id": "operator", "email": "operator@lmcp.local", "display_name": "Operator", "role": AuthRole.OPERATOR.value, "password": "operator"},
    {"user_id": "governance", "email": "governance@lmcp.local", "display_name": "Governance", "role": AuthRole.GOVERNANCE.value, "password": "governance"},
    {"user_id": "readonly", "email": "readonly@lmcp.local", "display_name": "Read Only", "role": AuthRole.READ_ONLY.value, "password": "read_only"},
)

