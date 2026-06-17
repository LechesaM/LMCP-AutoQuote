from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_batch_runner_invokes_each_pilot(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_workspace_pilot_batch.py"), "run_workspace_pilot_batch")
    calls = []

    def _fake_run_workspace_pilot_main(argv):
        calls.append(list(argv))
        return 0 if "PILOT-001" in argv else 1

    monkeypatch.setattr(module, "run_workspace_pilot_main", _fake_run_workspace_pilot_main)

    exit_code = module.main(["--workspace-root", str(tmp_path / "lmcp_pilot_runs")])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert len(calls) == 3
    assert calls[0][calls[0].index("--pilot-id") + 1] == "PILOT-001"
    assert calls[1][calls[1].index("--pilot-id") + 1] == "PILOT-002"
    assert calls[2][calls[2].index("--pilot-id") + 1] == "PILOT-003"
    parsed = json.loads(output)
    assert parsed["pilot_ids"] == ["PILOT-001", "PILOT-002", "PILOT-003"]
    assert parsed["overall_exit_code"] == 1
