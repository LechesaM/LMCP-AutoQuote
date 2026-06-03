from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_start_local_manual_production_script_is_self_seeding_and_shell_safe() -> None:
    script = ROOT / "scripts" / "start_local_manual_production.sh"
    text = script.read_text(encoding="utf-8").lower()

    assert "lmcp_project_root" in text
    assert "lmcp_runtime_dir" in text
    assert "lmcp_manual_production_dir" in text
    assert "lmcp_manual_production_db_path" in text
    assert "lmcp_app_entrypoint" in text
    assert "lmcp_allow_degraded_startup" in text
    assert "lmcp_local_backend_host" in text
    assert "lmcp_local_frontend_host" in text
    assert "127.0.0.1" in text
    assert "--strictport" in text

    subprocess.run(["bash", "-n", str(script)], check=True)
