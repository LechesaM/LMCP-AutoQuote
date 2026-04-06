from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.services.supplier_quote_ingestion_service import extract_and_compare_supplier_quotes

logger = logging.getLogger(__name__)


class SupplierPriceSelectionService:
    """
    Reads supplier quote PDFs already stored in a monthly_quotes folder,
    extracts/comparers supplier prices, then maps the best prices back into
    the RFQ/pricing structure used by the LMCP tender pipeline.

    Main responsibilities:
    1. Build quote_comparison.json from supplier PDFs
    2. Select cheapest valid supplier pricing per item
    3. Apply LMCP markup/margin
    4. Return pricing payload ready for quote generation
    """

    DEFAULT_MARGIN = 0.25
    DEFAULT_MIN_PROFIT = 30000.0

    @classmethod
    def enrich_pipeline_result_with_supplier_prices(
        cls,
        result: Dict[str, Any],
        folder_path: str | Path,
        *,
        margin: Optional[float] = None,
        minimum_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point for tender pipeline integration.

        Expected:
            result["rfq"]["items"] or result["items"] = list of RFQ items

        Adds:
            result["supplier_quote_comparison"]
            result["supplier_quote_comparison_path"]
            result["supplier_pricing_used"]
            result["supplier_pricing_summary"]
            result["pricing_items"]
            result["estimated_cost"]
            result["estimated_sell_total"]
            result["estimated_profit"]
            result["meets_minimum_profit"]
        """
        result = result or {}
        folder = Path(folder_path)

        if not folder.exists() or not folder.is_dir():
            result["supplier_pricing_used"] = False
            result["supplier_pricing_error"] = f"Folder not found: {folder}"
            return result

        comparison_result = extract_and_compare_supplier_quotes(folder)

        result["supplier_quote_comparison"] = comparison_result.get("comparison")
        result["supplier_quote_comparison_path"] = comparison_result.get("comparison_path")
        result["supplier_quote_extraction_results"] = comparison_result.get("results", [])

        comparison = comparison_result.get("comparison") or {}
        comparison_items = comparison.get("items") or []

        if not comparison_items:
            result["supplier_pricing_used"] = False
            result["supplier_pricing_error"] = "No comparable supplier pricing items found."
            return result

        rfq_items = cls._get_rfq_items(result)
        if not rfq_items:
            result["supplier_pricing_used"] = False
            result["supplier_pricing_error"] = "No RFQ items found in pipeline result."
            return result

        margin = float(margin if margin is not None else cls.DEFAULT_MARGIN)
        minimum_profit = float(minimum_profit if minimum_profit is not None else cls.DEFAULT_MIN_PROFIT)

        matched_items: List[Dict[str, Any]] = []
        unmatched_items: List[Dict[str, Any]] = []

        total_cost = 0.0
        total_sell = 0.0

        for rfq_item in rfq_items:
            matched = cls._match_rfq_item_to_comparison(rfq_item, comparison_items)

            if not matched:
                unmatched_items.append({
                    "rfq_item": rfq_item,
                    "reason": "No supplier comparison match found.",
                })
                continue

            qty = cls._extract_quantity(rfq_item)
            if qty is None or qty <= 0:
                qty = matched.get("quantity_reference") or 1.0

            cheapest_unit_price = matched.get("cheapest_unit_price")
            cheapest_supplier = matched.get("cheapest_supplier")

            if cheapest_unit_price is None or cheapest_unit_price <= 0:
                unmatched_items.append({
                    "rfq_item": rfq_item,
                    "reason": "Matched item has no valid cheapest unit price.",
                    "matched_comparison_item": matched,
                })
                continue

            cost_total = round(float(qty) * float(cheapest_unit_price), 2)
            sell_unit_price = cls._apply_margin(cheapest_unit_price, margin)
            sell_total = round(float(qty) * float(sell_unit_price), 2)
            profit = round(sell_total - cost_total, 2)

            mapped = {
                "description": cls._extract_description(rfq_item),
                "normalized_description": matched.get("normalized_description"),
                "quantity": qty,
                "unit": cls._extract_unit(rfq_item) or cls._infer_unit_from_comparison(matched),
                "supplier_name": cheapest_supplier,
                "supplier_unit_price": round(float(cheapest_unit_price), 2),
                "supplier_total": cost_total,
                "lmcp_unit_price": sell_unit_price,
                "lmcp_total": sell_total,
                "profit": profit,
                "source_match_score": matched.get("_match_score"),
                "comparison_suppliers": matched.get("suppliers"),
            }

            matched_items.append(mapped)
            total_cost += cost_total
            total_sell += sell_total

        total_cost = round(total_cost, 2)
        total_sell = round(total_sell, 2)
        total_profit = round(total_sell - total_cost, 2)

        result["supplier_pricing_used"] = len(matched_items) > 0
        result["supplier_pricing_summary"] = {
            "matched_item_count": len(matched_items),
            "unmatched_item_count": len(unmatched_items),
            "margin_used": margin,
            "minimum_profit_required": minimum_profit,
        }

        result["pricing_items"] = matched_items
        result["supplier_unmatched_items"] = unmatched_items
        result["estimated_cost"] = total_cost
        result["estimated_sell_total"] = total_sell
        result["estimated_profit"] = total_profit
        result["meets_minimum_profit"] = total_profit >= minimum_profit

        # Optional compatibility fields for your downstream quote pack service
        result["quote_total_cost"] = total_cost
        result["quote_subtotal"] = total_sell
        result["quote_total"] = total_sell

        # Convenience buyer/supplier selection summary
        recommended_supplier = (comparison.get("recommended_supplier_by_total") or {}).get("supplier_name")
        result["recommended_supplier_by_total"] = recommended_supplier

        return result

    # -----------------------------------------------------------------
    # RFQ matching
    # -----------------------------------------------------------------

    @classmethod
    def _match_rfq_item_to_comparison(
        cls,
        rfq_item: Dict[str, Any],
        comparison_items: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        rfq_desc = cls._normalize_text(cls._extract_description(rfq_item))
        if not rfq_desc:
            return None

        best_match = None
        best_score = 0.0

        for comp in comparison_items:
            comp_desc = cls._normalize_text(comp.get("normalized_description"))
            if not comp_desc:
                continue

            score = cls._similarity_score(rfq_desc, comp_desc)

            # small bonus if quantities align
            rfq_qty = cls._extract_quantity(rfq_item)
            comp_qty = comp.get("quantity_reference")
            if rfq_qty and comp_qty:
                try:
                    if abs(float(rfq_qty) - float(comp_qty)) < 0.001:
                        score += 0.05
                except Exception:
                    pass

            if score > best_score:
                best_score = score
                best_match = dict(comp)
                best_match["_match_score"] = round(score, 4)

        if best_match and best_score >= 0.45:
            return best_match

        return None

    @classmethod
    def _similarity_score(cls, a: str, b: str) -> float:
        """
        Lightweight token-overlap similarity.
        """
        a_tokens = set(a.split())
        b_tokens = set(b.split())

        if not a_tokens or not b_tokens:
            return 0.0

        intersection = len(a_tokens & b_tokens)
        union = len(a_tokens | b_tokens)
        jaccard = intersection / union if union else 0.0

        # containment bonus
        containment = 0.0
        if a in b or b in a:
            containment = 0.20

        # token length closeness bonus
        len_bonus = 0.0
        diff = abs(len(a_tokens) - len(b_tokens))
        if diff == 0:
            len_bonus = 0.05
        elif diff == 1:
            len_bonus = 0.03

        return min(jaccard + containment + len_bonus, 1.0)

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    @classmethod
    def _get_rfq_items(cls, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        rfq = result.get("rfq") if isinstance(result.get("rfq"), dict) else {}

        items = rfq.get("items")
        if isinstance(items, list) and items:
            return [i for i in items if isinstance(i, dict)]

        items = result.get("items")
        if isinstance(items, list) and items:
            return [i for i in items if isinstance(i, dict)]

        buyer_schedule = result.get("buyer_pricing_schedule")
        if isinstance(buyer_schedule, list) and buyer_schedule:
            return [i for i in buyer_schedule if isinstance(i, dict)]

        return []

    @classmethod
    def _extract_description(cls, item: Dict[str, Any]) -> str:
        for key in [
            "description",
            "item_description",
            "specification",
            "name",
            "title",
            "product_name",
        ]:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @classmethod
    def _extract_quantity(cls, item: Dict[str, Any]) -> Optional[float]:
        for key in ["quantity", "qty", "required_quantity", "units_required"]:
            value = item.get(key)
            if value is None:
                continue
            try:
                return float(str(value).replace(",", "."))
            except Exception:
                continue
        return None

    @classmethod
    def _extract_unit(cls, item: Dict[str, Any]) -> Optional[str]:
        for key in ["unit", "uom", "measure_unit"]:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @classmethod
    def _infer_unit_from_comparison(cls, matched: Dict[str, Any]) -> Optional[str]:
        suppliers = matched.get("suppliers") or {}
        for _, supplier_row in suppliers.items():
            unit = supplier_row.get("unit")
            if isinstance(unit, str) and unit.strip():
                return unit.strip()
        return None

    @classmethod
    def _apply_margin(cls, supplier_unit_price: float, margin: float) -> float:
        supplier_unit_price = float(supplier_unit_price)
        margin = max(0.0, float(margin))
        return round(supplier_unit_price * (1.0 + margin), 2)

    @classmethod
    def _normalize_text(cls, text: str) -> str:
        text = (text or "").lower()
        text = re.sub(r"[^a-z0-9 ]+", " ", text)
        text = re.sub(r"\b(the|and|for|with|of|to|ea|each|unit|units|pcs|pc)\b", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
