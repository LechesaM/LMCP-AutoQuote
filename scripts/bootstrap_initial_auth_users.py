#!/usr/bin/env python3
from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.auth import create_user
from app.auth.session_service import list_users

INITIAL_USERS = [
    {
        "user_id": "live-supervisor-1",
        "email": "live.supervisor@lmcp.local",
        "display_name": "Live Supervisor",
        "role": "supervisor",
    },
    {
        "user_id": "live-operator-1",
        "email": "live.operator1@lmcp.local",
        "display_name": "Live Operator 1",
        "role": "operator",
    },
    {
        "user_id": "live-operator-2",
        "email": "live.operator2@lmcp.local",
        "display_name": "Live Operator 2",
        "role": "operator",
    },
    {
        "user_id": "live-operator-3",
        "email": "live.operator3@lmcp.local",
        "display_name": "Live Operator 3",
        "role": "operator",
    },
    {
        "user_id": "live-governance-1",
        "email": "live.governance@lmcp.local",
        "display_name": "Live Governance",
        "role": "governance",
    },
]


def main() -> int:
    created = []
    existing = []
    users = {user.email.lower(): user for user in list_users()}

    for user in INITIAL_USERS:
        email = user["email"].lower()
        if email in users:
            existing.append(
                {
                    "user_id": users[email].user_id,
                    "email": users[email].email,
                    "display_name": users[email].display_name,
                    "role": users[email].role,
                    "status": "existing",
                }
            )
            continue

        password = secrets.token_urlsafe(12)
        record = create_user(
            user["user_id"],
            user["email"],
            user["display_name"],
            user["role"],
            password,
            overwrite=False,
        )
        created.append(
            {
                "user_id": record.user_id,
                "email": record.email,
                "display_name": record.display_name,
                "role": record.role,
                "password": password,
                "status": "created",
            }
        )

    payload = {
        "status": "ok",
        "created_count": len(created),
        "existing_count": len(existing),
        "created": created,
        "existing": existing,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
