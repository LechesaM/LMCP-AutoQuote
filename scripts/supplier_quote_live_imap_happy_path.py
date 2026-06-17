from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.supplier_quote_ingestion_service import SupplierQuoteIngestionService


def main() -> int:
    service = SupplierQuoteIngestionService()
    if not service.is_configured():
        print(
            json.dumps(
                {
                    "stage": "supplier_quote_live_imap_happy_path",
                    "status": "skipped",
                    "reason": "IMAP credentials not configured",
                    "configured": False,
                    "enabled": service.enabled,
                    "credential_source": service.credential_source,
                    "imap_host": service.imap_host,
                    "imap_port": service.imap_port,
                },
                indent=2,
            )
        )
        return 0

    result = service.ingest_once()
    probe = result.get("imap_probe") if isinstance(result.get("imap_probe"), dict) else {}
    workspace = result.get("workspace")
    summary = {
        "stage": "supplier_quote_live_imap_happy_path",
        "configured": True,
        "enabled": service.enabled,
        "credential_source": getattr(service, "credential_source", ""),
        "imap_probe_status": probe.get("status"),
        "imap_probe_message": probe.get("message"),
        "status": result.get("status"),
        "success": bool(result.get("success")),
        "processed": int(result.get("processed") or 0),
        "saved_attachments": int(result.get("saved_attachments") or 0),
        "workspace": workspace,
        "reason": result.get("reason"),
        "submission_ready": bool(result.get("submission_ready")),
        "review_ready": bool(result.get("review_ready")),
    }

    if workspace:
        summary["workspace_exists"] = Path(str(workspace)).exists()
    if probe.get("status") == "ok":
        summary["message_count"] = int(probe.get("message_count") or 0)
    if result.get("status") == "empty" and probe.get("status") == "ok":
        summary["status"] = "empty"
        summary["success"] = True
        summary["treat_as_pass"] = True
        summary["pass_reason"] = "IMAP probe succeeded and no new matching supplier quote messages were available."

    print(json.dumps(summary, indent=2))

    if result.get("status") == "failed":
        return 1
    if probe.get("status") != "ok":
        return 1
    if workspace and not Path(str(workspace)).exists():
        return 1
    if result.get("status") == "empty" and probe.get("status") == "ok":
        return 0
    if not result.get("submission_ready"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
