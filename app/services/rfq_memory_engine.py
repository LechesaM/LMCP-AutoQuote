from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, Any, List

MEMORY_FILE = "app/data/rfq_memory.json"


class RFQMemoryEngine:

    # ==============================
    # LOAD / SAVE
    # ==============================
    @staticmethod
    def _load_memory() -> Dict[str, Any]:
        if not os.path.exists(MEMORY_FILE):
            return {"rfqs": [], "buyers": {}, "items": {}}

        try:
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {"rfqs": [], "buyers": {}, "items": {}}

    @staticmethod
    def _save_memory(data: Dict[str, Any]):
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        with open(MEMORY_FILE, "w") as f:
            json.dump(data, f, indent=2)

    # ==============================
    # STORE RFQ
    # ==============================
    @staticmethod
    def store_rfq(rfq: Dict[str, Any]) -> None:
        memory = RFQMemoryEngine._load_memory()

        buyer = rfq.get("buyer_name", "unknown")
        rfq_number = rfq.get("buyer_rfq_number") or rfq.get("rfq_number")

        record = {
            "buyer": buyer,
            "rfq_number": rfq_number,
            "items": rfq.get("items", []),
            "submission_method": rfq.get("submission_method"),
            "timestamp": datetime.utcnow().isoformat(),
            "quote_ready": rfq.get("quote_ready", False),
            "won": rfq.get("won", False)
        }

        memory["rfqs"].append(record)

        # ------------------------------
        # UPDATE BUYER PROFILE
        # ------------------------------
        buyer_profile = memory["buyers"].setdefault(buyer, {
            "total_rfqs": 0,
            "wins": 0,
            "preferred_submission": {},
            "items_frequency": {}
        })

        buyer_profile["total_rfqs"] += 1
        if record["won"]:
            buyer_profile["wins"] += 1

        sub_method = record["submission_method"]
        if sub_method:
            buyer_profile["preferred_submission"][sub_method] = \
                buyer_profile["preferred_submission"].get(sub_method, 0) + 1

        # ------------------------------
        # UPDATE ITEM MEMORY
        # ------------------------------
        for item in record["items"]:
            name = item.get("description", "").lower().strip()
            price = item.get("unit_price", 0)

            if not name:
                continue

            item_mem = memory["items"].setdefault(name, {
                "count": 0,
                "avg_price": 0
            })

            item_mem["count"] += 1
            item_mem["avg_price"] = (
                (item_mem["avg_price"] * (item_mem["count"] - 1)) + price
            ) / item_mem["count"]

        RFQMemoryEngine._save_memory(memory)

    # ==============================
    # GET BUYER INSIGHTS
    # ==============================
    @staticmethod
    def get_buyer_insights(buyer_name: str) -> Dict[str, Any]:
        memory = RFQMemoryEngine._load_memory()
        return memory["buyers"].get(buyer_name, {})

    # ==============================
    # SUGGEST PRICING
    # ==============================
    @staticmethod
    def suggest_price(item_name: str) -> float:
        memory = RFQMemoryEngine._load_memory()
        item = memory["items"].get(item_name.lower().strip())

        if not item:
            return 0

        return round(item.get("avg_price", 0), 2)

    # ==============================
    # ENHANCE RFQ BEFORE QUOTING
    # ==============================
    @staticmethod
    def enhance_rfq(rfq: Dict[str, Any]) -> Dict[str, Any]:
        for item in rfq.get("items", []):
            if not item.get("unit_price"):
                suggested = RFQMemoryEngine.suggest_price(item.get("description", ""))
                if suggested > 0:
                    item["unit_price"] = suggested
                    item["price_source"] = "memory_engine"

        return rfq
