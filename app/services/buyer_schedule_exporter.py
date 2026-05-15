from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


class BuyerScheduleExporter:
    @staticmethod
    def export_json(
        completed_schedule: Dict[str, Any],
        output_dir: str,
        rfq_number: str | None = None,
    ) -> str:
        base_dir = Path(output_dir)
        base_dir.mkdir(parents=True, exist_ok=True)

        ref = (rfq_number or completed_schedule.get("rfq_number") or "rfq").replace("/", "-").replace("\\", "-")
        filename = f"buyer_pricing_schedule_{ref}_{_now_stamp()}.json"
        file_path = base_dir / filename

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(completed_schedule, f, indent=2, ensure_ascii=False)

        return str(file_path)
