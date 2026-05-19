export const AUTH_ROLES = {
  admin: "admin",
  supervisor: "supervisor",
  operator: "operator",
  governance: "governance",
  read_only: "read_only",
};

export const ROLE_LABELS = {
  admin: "Admin",
  supervisor: "Supervisor",
  operator: "Operator",
  governance: "Governance",
  read_only: "Read Only",
};

export const ROLE_PERMISSIONS = {
  admin: [
    "view_dashboard",
    "view_rfqs",
    "view_operator_queue",
    "assign_operator",
    "mark_reviewed",
    "escalate_review",
    "archive_rfq",
    "acknowledge_alert",
    "view_audit",
    "view_governance",
    "manage_sources",
    "manage_users",
  ],
  supervisor: [
    "view_dashboard",
    "view_rfqs",
    "view_operator_queue",
    "assign_operator",
    "mark_reviewed",
    "escalate_review",
    "archive_rfq",
    "acknowledge_alert",
    "view_audit",
    "view_governance",
  ],
  operator: ["view_dashboard", "view_rfqs", "view_operator_queue", "mark_reviewed", "acknowledge_alert"],
  governance: ["view_dashboard", "view_rfqs", "view_operator_queue", "view_audit", "view_governance", "acknowledge_alert"],
  read_only: ["view_dashboard", "view_rfqs", "view_operator_queue", "view_audit", "view_governance"],
};

export function canRoleAccess(role, permission) {
  return (ROLE_PERMISSIONS[String(role || "").toLowerCase()] || []).includes(permission);
}

