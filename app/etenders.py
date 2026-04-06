from __future__ import annotations

from typing import Any, Dict, List


def list_releases() -> List[Dict[str, Any]]:
    """
    Placeholder implementation.
    This keeps the module syntactically valid until a real eTenders
    integration is completed.
    """
    return []


def get_status() -> Dict[str, Any]:
    releases = list_releases()
    return {
        "ok": True,
        "source": "etenders",
        "release_count": len(releases),
        "releases": releases,
    }
