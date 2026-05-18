from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class UnmatchedSupplierReplyService:
    DEFAULT_BASE_DIR = "monthly_quotes/unmatched_supplier_quotes"

    @classmethod
    def _safe_str(cls, value: Any, default: str = "") -> str:
        if value is None:
            return default
        text = str(value).strip()
        return text if text else default

    @classmethod
    def _base_dir(cls) -> Path:
        base = Path(cls.DEFAULT_BASE_DIR)
        base.mkdir(parents=True, exist_ok=True)
        return base

    @classmethod
    def _month_dir(cls) -> Path:
        month_dir = cls._base_dir() / datetime.now().strftime("%Y-%m")
        month_dir.mkdir(parents=True, exist_ok=True)
        return month_dir

    @classmethod
    def store_unmatched_reply(
        cls,
        *,
        email_id: str,
        from_email: str,
        from_name: str,
        subject: str,
        received_date: str,
        attachment_names: Optional[List[str]] = None,
        reason: str = "unmatched_reply",
        body_excerpt: str = "",
    ) -> Dict[str, Any]:
        folder_name = f"{email_id or 'unknown_email'}"
        folder = cls._month_dir() / folder_name
        folder.mkdir(parents=True, exist_ok=True)

        payload = {
            "email_id": cls._safe_str(email_id),
            "from_email": cls._safe_str(from_email),
            "from_name": cls._safe_str(from_name),
            "subject": cls._safe_str(subject),
            "received_date": cls._safe_str(received_date),
            "attachment_names": attachment_names or [],
            "reason": cls._safe_str(reason),
            "body_excerpt": cls._safe_str(body_excerpt)[:2000],
            "stored_at": datetime.now().isoformat(),
        }

        metadata_path = folder / "unmatched_reply.json"
        metadata_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        return {
            "success": True,
            "folder": str(folder),
            "metadata_path": str(metadata_path),
            "payload": payload,
        }
