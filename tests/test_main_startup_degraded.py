from __future__ import annotations

import asyncio
from types import SimpleNamespace

from sqlalchemy.exc import OperationalError

import app.main as main


def test_lifespan_enters_degraded_mode_when_database_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(main, "ensure_operator_auth_schema", lambda: None)
    monkeypatch.setattr(
        main,
        "ensure_quote_pack_schema",
        lambda: (_ for _ in ()).throw(OperationalError("select 1", {}, Exception("boom"))),
    )

    app = SimpleNamespace(
        state=SimpleNamespace(
            router_report={"loaded": [], "failures": [], "duplicates": []},
        )
    )

    async def run() -> None:
        async with main.lifespan(app):
            pass

    asyncio.run(run())

    assert app.state.database_startup_degraded is True
    assert "boom" in app.state.database_startup_error
