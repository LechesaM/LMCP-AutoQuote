from __future__ import annotations

from app.source_registry import get_active_sources


def load_source_registry():
    class _Registry:
        def add_source(self, *_args, **_kwargs):
            return None

    return _Registry()
