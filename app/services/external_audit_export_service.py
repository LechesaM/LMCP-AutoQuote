from __future__ import annotations

import json
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from app.core.runtime_paths import get_runtime_paths


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _workspace(tender_id: str) -> Path:
    return get_runtime_paths().manual_production_dir / "submission_executions" / tender_id


def build_external_audit_export_report(detail: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(detail or {})
    tender_id = _clean(payload.get("tender_id") or "RFQ")
    workspace = _workspace(tender_id)
    export_dir = workspace / "external_audit_export"
    export_dir.mkdir(parents=True, exist_ok=True)
    zip_path = export_dir / f"{tender_id}__external_audit_export.zip"
    manifest_path = export_dir / f"{tender_id}__external_audit_export_manifest.json"
    manifest = {
        "tender_id": tender_id,
        "generated_at": _now_iso(),
        "status": "ready",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
    return {
        "tender_id": tender_id,
        "ready": True,
        "status": "ok",
        "export": {
            "zipPath": str(zip_path),
            "manifestPath": str(manifest_path),
        },
        "blockers": [],
    }
