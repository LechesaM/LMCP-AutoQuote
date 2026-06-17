from __future__ import annotations

"""
Unsupported legacy root-level router modules.

These modules remain in the repository for historical compatibility, but they are
not part of the active router registry and should not be treated as production
runtime surfaces.
"""

QUARANTINED_ROOT_ROUTER_MODULES = (
    "app.dashboard_api",
    "app.quote_api",
    "app.quotes_api",
    "app.submission_api",
    "app.system_routes",
)

