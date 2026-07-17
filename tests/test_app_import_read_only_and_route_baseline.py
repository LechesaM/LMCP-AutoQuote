from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path


def _run_import_probe(openapi: bool = False):
    code = f"""
from pathlib import Path
import json
import os
mkdir_calls = []
write_calls = []
replace_calls = []
Path.mkdir = lambda self,*a,**kw: mkdir_calls.append(str(self)) or None
Path.write_text = lambda self,*a,**kw: write_calls.append(['write_text', str(self)]) or 0
Path.write_bytes = lambda self,*a,**kw: write_calls.append(['write_bytes', str(self)]) or 0
os.replace = lambda src,dst,*a,**kw: replace_calls.append([str(src), str(dst)]) or None
import app.main
{"app.main.app.openapi()" if openapi else ""}
print(json.dumps({{'mkdir': mkdir_calls, 'write': write_calls, 'replace': replace_calls}}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(Path(__file__).resolve().parents[1]),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_import_app_main_has_no_persistent_writes():
    result = _run_import_probe(openapi=False)
    assert result == {"mkdir": [], "write": [], "replace": []}


def test_openapi_generation_has_no_persistent_writes():
    result = _run_import_probe(openapi=True)
    assert result == {"mkdir": [], "write": [], "replace": []}


def test_explicit_startup_directory_initialization_is_idempotent(tmp_path, monkeypatch):
    import app.main as main

    dirs = [tmp_path / "runtime", tmp_path / "monthly_quotes", tmp_path / "runtime" / "proofs"]
    monkeypatch.setattr(main, "RUNTIME_STATIC_DIRS", dirs)

    first = main.initialize_runtime_static_dirs()
    second = main.initialize_runtime_static_dirs()

    assert first["status"] == "ok"
    assert second["status"] == "ok"
    assert all(path.is_dir() for path in dirs)


def test_high_risk_router_families_disabled_by_default():
    import app.main as main

    disabled = {name for name, _reason in main.disabled_routers}
    expected = {
        "auto_submission_v46_router",
        "portal_submission_v47_router",
        "smart_upload_v47_4_router",
        "final_submission_v47_5_router",
        "full_autonomous_v48_router",
        "smart_harvester_v31_router",
        "etenders_document_download_v50_9_router",
    }
    assert expected.issubset(disabled)
    assert main.failed_routers == []


def test_required_route_families_remain_registered():
    from app.main import app

    paths = set(app.openapi()["paths"])
    required = {
        "/health",
        "/health/workflows",
        "/system/control/status",
        "/system/control/effective-status",
        "/rfq-lifecycle/status",
        "/rfq-lifecycle/manual-pricing/{rfq_id}",
        "/quote-compilation/candidates",
        "/sbd-intelligence/status",
        "/tender-form-intelligence/status",
    }
    assert required.issubset(paths)


def test_no_duplicate_method_path_pairs():
    from app.main import app

    pairs = []
    for path, operations in app.openapi()["paths"].items():
        for method in operations:
            upper = method.upper()
            if upper in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                pairs.append((upper, path))
    counts = Counter(pairs)
    assert not [pair for pair, count in counts.items() if count > 1]


def test_route_baseline_json_validates():
    baseline_path = Path("config/lmcp_v2_operational_route_baseline.json")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert baseline["version"] == "lmcp-v2-operational-route-baseline"
    assert baseline["families"]
    statuses = {family["status"] for family in baseline["families"]}
    assert "REQUIRED" in statuses
    assert "DISABLED_BY_DEFAULT" in statuses


def test_router_activation_specific_opt_in(monkeypatch):
    monkeypatch.setenv("LMCP_ENABLE_ROUTER_FAMILIES", "auto_submission_v46_router")
    module = importlib.reload(importlib.import_module("app.core.router_activation"))
    assert module.is_router_family_enabled("auto_submission_v46_router") is True
    assert module.is_router_family_enabled("final_submission_v47_5_router") is False
