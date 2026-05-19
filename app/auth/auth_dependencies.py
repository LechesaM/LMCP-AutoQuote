from __future__ import annotations

from app.auth.auth_service import get_current_auth_context, require_permission, require_role


def current_user(request):
    return get_current_auth_context(request)


__all__ = ["current_user", "require_permission", "require_role"]

