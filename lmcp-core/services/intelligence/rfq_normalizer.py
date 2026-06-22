from __future__ import annotations


class RFQNormalizer:

    @staticmethod
    def normalize(rfq: dict) -> dict:
        return {
            "title": rfq.get("title"),
            "buyer_name": rfq.get("buyer_name") or rfq.get("issuing_entity"),
            "rfq_number": rfq.get("rfq_number") or rfq.get("reference_number"),
            "currency": "ZAR",
            "vat_percent": 15,
            "default_markup_percent": 25,
            "quote_ready": rfq.get("quote_ready", False),
            "line_items": rfq.get("line_items", []),
        }
