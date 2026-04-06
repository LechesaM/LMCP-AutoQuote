# app/services/intelligence_quote_pipeline.py

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

MIN_SCORE_FOR_QUOTE = float(os.getenv("MIN_SCORE_FOR_QUOTE", "70"))
MAX_PRODUCTS_PER_MATCH = int(os.getenv("MAX_PRODUCTS_PER_MATCH", "8"))
DEFAULT_MARKUP_PERCENT = float(os.getenv("DEFAULT_MARKUP_PERCENT", "18"))
DEFAULT_VAT_PERCENT = float(os.getenv("DEFAULT_VAT_PERCENT", "15"))
ENABLE_VAT = os.getenv("ENABLE_VAT", "true").strip().lower() in {
    "1", "true", "yes", "y", "on"
}

# -----------------------------------------------------------------------------
# Data models
# -----------------------------------------------------------------------------

@dataclass
class SupplierProductCandidate:
    supplier_name: str
    product_name: str
    sku: Optional[str]
    unit: Optional[str]
    category: Optional[str]
    brand: Optional[str]
    unit_cost: float
    currency: str
    lead_time_days: Optional[int]
    min_order_qty: Optional[float]
    pack_size: Optional[str]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# -----------------------------------------------------------------------------
# Text helpers
# -----------------------------------------------------------------------------

def _norm(text: Any) -> str:
    if text is None:
        return ""
    text = str(text).strip().lower()
    text = re.sub(r"[^a-z0-9\s/&\-.]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(text: Any) -> List[str]:
    normalized = _norm(text)
    if not normalized:
        return []
    return [t for t in normalized.split(" ") if len(t) >= 2]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _first_nonempty(*values: Any) -> Optional[str]:
    for value in values:
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return None


# -----------------------------------------------------------------------------
# Opportunity helpers
# -----------------------------------------------------------------------------

def _extract_score(opportunity: Dict[str, Any]) -> float:
    for key in (
        "score",
        "opportunity_score",
        "relevance_score",
        "weighted_score",
        "final_score",
    ):
        if key in opportunity:
            return _safe_float(opportunity.get(key), 0.0)
    return 0.0


def _opportunity_text(opportunity: Dict[str, Any]) -> str:
    return " ".join(
        [
            str(opportunity.get("title") or ""),
            str(opportunity.get("description") or ""),
            str(opportunity.get("category") or ""),
            str(opportunity.get("buyer_name") or ""),
            str(opportunity.get("reference_number") or ""),
        ]
    ).strip()


def _derive_requested_items(opportunity: Dict[str, Any]) -> List[str]:
    text = _norm(_opportunity_text(opportunity))
    requested: List[str] = []

    patterns = [
        ("laptop", ["laptop", "notebook computer"]),
        ("printer", ["printer", "multifunction printer"]),
        ("desktop", ["desktop", "computer"]),
        ("stationery", ["stationery", "office supplies"]),
        ("furniture", ["office furniture", "furniture"]),
        ("ppe", ["ppe", "personal protective equipment"]),
        ("uniform", ["uniform", "protective clothing"]),
        ("medical", ["medical supplies", "medical consumables"]),
        ("consumables", ["consumables"]),
        ("it equipment", ["it equipment", "ict equipment"]),
        ("cleaning", ["cleaning materials", "cleaning supplies"]),
        ("vehicle", ["vehicle", "fleet vehicle"]),
        ("tyres", ["tyres", "tires"]),
        ("generator", ["generator"]),
        ("solar", ["solar equipment", "inverter", "battery"]),
        ("water", ["water treatment chemicals", "water equipment"]),
        ("pipes", ["pipes", "fittings", "valves"]),
        ("electrical", ["electrical materials", "cables", "switchgear"]),
    ]

    for key, aliases in patterns:
        if key in text:
            requested.extend(aliases)

    if not requested:
        title = str(opportunity.get("title") or "").strip()
        if title:
            requested.append(title)

    deduped: List[str] = []
    seen = set()
    for item in requested:
        token = _norm(item)
        if token and token not in seen:
            seen.add(token)
            deduped.append(item)

    return deduped[:10]


# -----------------------------------------------------------------------------
# Supplier product loading
# -----------------------------------------------------------------------------

def _load_supplier_products_from_model(db: Any) -> List[Dict[str, Any]]:
    """
    Safe DB loader.
    This function tries common SQLAlchemy patterns without forcing a hard model dependency.
    """
    if db is None:
        return []

    candidates: List[Dict[str, Any]] = []

    model_paths = [
        ("app.models.supplier_product", "SupplierProduct"),
        ("app.models.supplier_products", "SupplierProduct"),
    ]

    for module_name, class_name in model_paths:
        try:
            module = __import__(module_name, fromlist=[class_name])
            model_cls = getattr(module, class_name, None)
            if model_cls is None:
                continue

            rows = db.query(model_cls).all()
            for row in rows:
                candidates.append(
                    {
                        "supplier_name": getattr(row, "supplier_name", None),
                        "product_name": getattr(row, "product_name", None),
                        "sku": getattr(row, "sku", None),
                        "unit": getattr(row, "unit", None),
                        "category": getattr(row, "category", None),
                        "brand": getattr(row, "brand", None),
                        "unit_cost": getattr(row, "unit_cost", None),
                        "currency": getattr(row, "currency", "ZAR"),
                        "lead_time_days": getattr(row, "lead_time_days", None),
                        "min_order_qty": getattr(row, "min_order_qty", None),
                        "pack_size": getattr(row, "pack_size", None),
                        "metadata": getattr(row, "extra_metadata", None) or {},                    }
                )

            if candidates:
                logger.info("Loaded %s supplier products from DB model.", len(candidates))
                return candidates

        except Exception as exc:
            logger.warning("Could not load supplier products via %s.%s: %s", module_name, class_name, exc)

    return []


def _fallback_supplier_products() -> List[Dict[str, Any]]:
    """
    Fallback catalogue so the quote pipeline still works even if DB products are empty.
    These are indicative and safe placeholders for commercial structuring.
    """
    return [
        {
            "supplier_name": "LMCP Preferred Supplier A",
            "product_name": "Business Laptop 15 inch",
            "sku": "IT-LAP-001",
            "unit": "each",
            "category": "IT / Technology",
            "brand": "Generic Business",
            "unit_cost": 12500.00,
            "currency": "ZAR",
            "lead_time_days": 7,
            "min_order_qty": 1,
            "pack_size": "1 unit",
            "metadata": {"keywords": ["laptop", "notebook", "computer", "it equipment"]},
        },
        {
            "supplier_name": "LMCP Preferred Supplier B",
            "product_name": "Office Multifunction Printer",
            "sku": "IT-PRN-001",
            "unit": "each",
            "category": "IT / Technology",
            "brand": "Generic Office",
            "unit_cost": 4800.00,
            "currency": "ZAR",
            "lead_time_days": 5,
            "min_order_qty": 1,
            "pack_size": "1 unit",
            "metadata": {"keywords": ["printer", "mfp", "multifunction printer"]},
        },
        {
            "supplier_name": "LMCP Preferred Supplier C",
            "product_name": "Stationery Mixed Office Pack",
            "sku": "STA-001",
            "unit": "pack",
            "category": "Office Supplies",
            "brand": "Office General",
            "unit_cost": 950.00,
            "currency": "ZAR",
            "lead_time_days": 3,
            "min_order_qty": 1,
            "pack_size": "bulk office pack",
            "metadata": {"keywords": ["stationery", "office supplies", "consumables"]},
        },
        {
            "supplier_name": "LMCP Preferred Supplier D",
            "product_name": "Office Desk and Chair Set",
            "sku": "FUR-001",
            "unit": "set",
            "category": "Furniture",
            "brand": "Workspace",
            "unit_cost": 3200.00,
            "currency": "ZAR",
            "lead_time_days": 10,
            "min_order_qty": 1,
            "pack_size": "1 set",
            "metadata": {"keywords": ["furniture", "desk", "chair", "office furniture"]},
        },
        {
            "supplier_name": "LMCP Preferred Supplier E",
            "product_name": "Protective PPE Kit",
            "sku": "PPE-001",
            "unit": "kit",
            "category": "Apparel / PPE",
            "brand": "SafetyPro",
            "unit_cost": 650.00,
            "currency": "ZAR",
            "lead_time_days": 4,
            "min_order_qty": 5,
            "pack_size": "1 full kit",
            "metadata": {"keywords": ["ppe", "protective equipment", "safety", "uniform"]},
        },
        {
            "supplier_name": "LMCP Preferred Supplier F",
            "product_name": "Medical Consumables Bulk Pack",
            "sku": "MED-001",
            "unit": "pack",
            "category": "Medical Supplies",
            "brand": "MediCore",
            "unit_cost": 2400.00,
            "currency": "ZAR",
            "lead_time_days": 6,
            "min_order_qty": 1,
            "pack_size": "bulk consumables",
            "metadata": {"keywords": ["medical", "medical supplies", "consumables"]},
        },
        {
            "supplier_name": "LMCP Preferred Supplier G",
            "product_name": "Cleaning Materials Starter Bundle",
            "sku": "CLN-001",
            "unit": "bundle",
            "category": "Consumables",
            "brand": "CleanPro",
            "unit_cost": 1800.00,
            "currency": "ZAR",
            "lead_time_days": 4,
            "min_order_qty": 1,
            "pack_size": "starter bundle",
            "metadata": {"keywords": ["cleaning", "cleaning materials", "cleaning supplies"]},
        },
        {
            "supplier_name": "LMCP Preferred Supplier H",
            "product_name": "Solar Backup Power Kit",
            "sku": "SOL-001",
            "unit": "kit",
            "category": "Equipment",
            "brand": "EnergyCore",
            "unit_cost": 28500.00,
            "currency": "ZAR",
            "lead_time_days": 14,
            "min_order_qty": 1,
            "pack_size": "complete kit",
            "metadata": {"keywords": ["solar", "inverter", "battery", "backup power"]},
        },
    ]


def load_supplier_products(db: Any = None) -> List[SupplierProductCandidate]:
    raw_rows = _load_supplier_products_from_model(db)

    if not raw_rows:
        raw_rows = _fallback_supplier_products()
        logger.info("Using fallback supplier catalogue with %s products.", len(raw_rows))

    products: List[SupplierProductCandidate] = []
    for row in raw_rows:
        products.append(
            SupplierProductCandidate(
                supplier_name=_first_nonempty(row.get("supplier_name"), "Unknown Supplier") or "Unknown Supplier",
                product_name=_first_nonempty(row.get("product_name"), "Unnamed Product") or "Unnamed Product",
                sku=_first_nonempty(row.get("sku")),
                unit=_first_nonempty(row.get("unit"), "each"),
                category=_first_nonempty(row.get("category"), "Supply / Delivery"),
                brand=_first_nonempty(row.get("brand")),
                unit_cost=_safe_float(row.get("unit_cost"), 0.0),
                currency=_first_nonempty(row.get("currency"), "ZAR") or "ZAR",
                lead_time_days=_safe_int(row.get("lead_time_days"), None),
                min_order_qty=_safe_float(row.get("min_order_qty"), 1.0),
                pack_size=_first_nonempty(row.get("pack_size")),
                metadata=row.get("metadata") or {},
            )
        )

    return products


# -----------------------------------------------------------------------------
# Matching engine
# -----------------------------------------------------------------------------

def _build_product_search_text(product: SupplierProductCandidate) -> str:
    parts = [
        product.product_name,
        product.category,
        product.brand,
        product.sku,
        product.pack_size,
    ]
    keywords = product.metadata.get("keywords", []) if isinstance(product.metadata, dict) else []
    if isinstance(keywords, list):
        parts.extend([str(k) for k in keywords])
    return " ".join([p for p in parts if p])


def _match_score(query: str, product: SupplierProductCandidate) -> float:
    query_tokens = set(_tokenize(query))
    product_tokens = set(_tokenize(_build_product_search_text(product)))

    if not query_tokens or not product_tokens:
        return 0.0

    overlap = query_tokens.intersection(product_tokens)
    score = float(len(overlap) * 10)

    if _norm(query) in _norm(product.product_name):
        score += 20

    if product.category and any(token in _norm(product.category) for token in query_tokens):
        score += 10

    if product.brand and any(token in _norm(product.brand) for token in query_tokens):
        score += 5

    return round(score, 2)


def match_supplier_products(
    db: Any,
    opportunity: Dict[str, Any],
    limit: int = MAX_PRODUCTS_PER_MATCH,
) -> List[Dict[str, Any]]:
    products = load_supplier_products(db)
    requested_items = _derive_requested_items(opportunity)

    scored_matches: List[Tuple[float, SupplierProductCandidate, str]] = []

    for requested in requested_items:
        for product in products:
            score = _match_score(requested, product)
            if score <= 0:
                continue
            scored_matches.append((score, product, requested))

    scored_matches.sort(key=lambda x: x[0], reverse=True)

    results: List[Dict[str, Any]] = []
    seen = set()

    for score, product, requested in scored_matches:
        key = (product.supplier_name, product.product_name, requested)
        if key in seen:
            continue
        seen.add(key)

        results.append(
            {
                "match_score": score,
                "matched_request": requested,
                "supplier_product": product.to_dict(),
            }
        )

        if len(results) >= limit:
            break

    return results


# -----------------------------------------------------------------------------
# Pricing engine
# -----------------------------------------------------------------------------

def _estimate_quantity(opportunity: Dict[str, Any]) -> float:
    text = _opportunity_text(opportunity)

    patterns = [
        r"\b(\d{1,5})\s*(units|unit|items|item|pcs|pieces|kits|kit|packs|set|sets|chairs|desks|laptops|printers)\b",
        r"\bquantity\s*[:=-]?\s*(\d{1,5})\b",
        r"\bqty\s*[:=-]?\s*(\d{1,5})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return max(1.0, _safe_float(match.group(1), 1.0))

    return 1.0


def _price_line(unit_cost: float, quantity: float) -> Dict[str, float]:
    base_cost = round(unit_cost * quantity, 2)
    markup_amount = round(base_cost * (DEFAULT_MARKUP_PERCENT / 100.0), 2)
    subtotal_excl_vat = round(base_cost + markup_amount, 2)

    vat_amount = round(subtotal_excl_vat * (DEFAULT_VAT_PERCENT / 100.0), 2) if ENABLE_VAT else 0.0
    total_incl_vat = round(subtotal_excl_vat + vat_amount, 2)

    return {
        "base_cost": base_cost,
        "markup_amount": markup_amount,
        "subtotal_excl_vat": subtotal_excl_vat,
        "vat_amount": vat_amount,
        "total_incl_vat": total_incl_vat,
    }


def build_pricing_summary(
    opportunity: Dict[str, Any],
    matched_products: List[Dict[str, Any]],
) -> Dict[str, Any]:
    quantity = _estimate_quantity(opportunity)

    if not matched_products:
        return {
            "pricing_model": "manual_supplier_pricing_required",
            "currency": "ZAR",
            "estimated_quantity": quantity,
            "matched_products_count": 0,
            "line_items": [],
            "totals": {
                "base_cost": 0.0,
                "markup_amount": 0.0,
                "subtotal_excl_vat": 0.0,
                "vat_amount": 0.0,
                "total_incl_vat": 0.0,
            },
            "notes": [
                "No supplier catalogue matches found.",
                "Manual sourcing and pricing confirmation required before quotation issue.",
            ],
        }

    line_items: List[Dict[str, Any]] = []
    total_base = 0.0
    total_markup = 0.0
    total_subtotal = 0.0
    total_vat = 0.0
    total_incl = 0.0

    for match in matched_products:
        supplier_product = match.get("supplier_product", {})
        unit_cost = _safe_float(supplier_product.get("unit_cost"), 0.0)
        price_info = _price_line(unit_cost=unit_cost, quantity=quantity)

        total_base += price_info["base_cost"]
        total_markup += price_info["markup_amount"]
        total_subtotal += price_info["subtotal_excl_vat"]
        total_vat += price_info["vat_amount"]
        total_incl += price_info["total_incl_vat"]

        line_items.append(
            {
                "supplier_name": supplier_product.get("supplier_name"),
                "product_name": supplier_product.get("product_name"),
                "sku": supplier_product.get("sku"),
                "unit": supplier_product.get("unit"),
                "category": supplier_product.get("category"),
                "brand": supplier_product.get("brand"),
                "estimated_quantity": quantity,
                "unit_cost": round(unit_cost, 2),
                "match_score": match.get("match_score", 0),
                "matched_request": match.get("matched_request"),
                **price_info,
            }
        )

    return {
        "pricing_model": "supplier_catalogue_estimate",
        "currency": "ZAR",
        "estimated_quantity": quantity,
        "matched_products_count": len(matched_products),
        "line_items": line_items,
        "totals": {
            "base_cost": round(total_base, 2),
            "markup_amount": round(total_markup, 2),
            "subtotal_excl_vat": round(total_subtotal, 2),
            "vat_amount": round(total_vat, 2),
            "total_incl_vat": round(total_incl, 2),
        },
        "notes": [
            "Pricing is derived from matched supplier catalogue entries.",
            "Final RFQ/RFT submission pricing should be validated against live supplier quotations.",
        ],
    }


# -----------------------------------------------------------------------------
# Compliance helper
# -----------------------------------------------------------------------------

def build_compliance_flags(opportunity: Dict[str, Any]) -> Dict[str, Any]:
    text = _norm(_opportunity_text(opportunity))

    flags = {
        "requires_csd": True,
        "requires_tax_clearance": True,
        "requires_bbee": True,
        "requires_sbd_forms": True,
        "requires_technical_datasheets": False,
        "requires_delivery_schedule": True,
        "requires_warranty_support": False,
    }

    if any(term in text for term in ["equipment", "generator", "solar", "printer", "laptop", "medical"]):
        flags["requires_technical_datasheets"] = True

    if any(term in text for term in ["warranty", "maintenance support", "after-sales"]):
        flags["requires_warranty_support"] = True

    return flags


# -----------------------------------------------------------------------------
# Quote payload builder
# -----------------------------------------------------------------------------

def build_quote_payload(
    opportunity: Dict[str, Any],
    matched_products: List[Dict[str, Any]],
) -> Dict[str, Any]:
    pricing_summary = build_pricing_summary(opportunity, matched_products)
    score = _extract_score(opportunity)

    return {
        "title": opportunity.get("title"),
        "reference_number": opportunity.get("reference_number"),
        "source_name": opportunity.get("source_name"),
        "external_url": opportunity.get("external_url"),
        "buyer_name": opportunity.get("buyer_name"),
        "category": opportunity.get("category"),
        "closing_date": opportunity.get("closing_date"),
        "score": score,
        "requested_items": _derive_requested_items(opportunity),
        "matched_products": matched_products,
        "pricing_summary": pricing_summary,
        "compliance_flags": build_compliance_flags(opportunity),
        "quote_readiness": {
            "commercial_ready": len(matched_products) > 0,
            "pricing_confidence": "medium" if len(matched_products) > 0 else "low",
            "supplier_match_count": len(matched_products),
        },
    }


# -----------------------------------------------------------------------------
# Main public pipeline
# -----------------------------------------------------------------------------

def process_high_score_opportunities(
    db: Any,
    scored_opportunities: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Main entry point used by autonomous_engine.py

    Returns a stable list of:
    {
        "status": "quote_ready",
        "opportunity": {...},
        "quote_payload": {...}
    }
    """
    if not isinstance(scored_opportunities, list):
        logger.warning("process_high_score_opportunities received non-list input.")
        return []

    results: List[Dict[str, Any]] = []

    for opportunity in scored_opportunities:
        try:
            if not isinstance(opportunity, dict):
                continue

            score = _extract_score(opportunity)
            if score < MIN_SCORE_FOR_QUOTE:
                continue

            matched_products = match_supplier_products(db, opportunity, limit=MAX_PRODUCTS_PER_MATCH)
            quote_payload = build_quote_payload(opportunity, matched_products)

            results.append(
                {
                    "status": "quote_ready",
                    "opportunity": opportunity,
                    "quote_payload": quote_payload,
                }
            )

        except Exception as exc:
            logger.exception("Quote pipeline failed for one opportunity but continued safely: %s", exc)
            continue

    logger.info("process_high_score_opportunities produced %s quote-ready results.", len(results))
    return results


# -----------------------------------------------------------------------------
# Optional helper for direct testing
# -----------------------------------------------------------------------------

def preview_quote_pipeline(
    db: Any,
    scored_opportunities: List[Dict[str, Any]],
) -> Dict[str, Any]:
    results = process_high_score_opportunities(db, scored_opportunities)
    return {
        "success": True,
        "count": len(results),
        "results": results,
    }


def _fallback_process_high_score_opportunities(
    db: Any,
    scored_opportunities: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Fallback processor for high scoring opportunities when supplier catalogue
    mapping is not yet available.

    This guarantees the LMCP AutoQuote system still produces commercially
    useful quote payloads.
    """

    results: List[Dict[str, Any]] = []

    for item in scored_opportunities:

        if not isinstance(item, dict):
            continue

        title = str(item.get("title") or "").strip()
        reference_number = str(item.get("reference_number") or "").strip()

        score = int(item.get("score") or item.get("intelligence_score") or 0)

        if score < 50:
            # Skip low-quality opportunities
            continue

        pricing_summary = {
            "pricing_model": "request_for_supplier_pricing",
            "basis": "commercial pricing to be generated from supplier catalogue mapping",
            "confidence": "medium" if score >= 80 else "preliminary",
        }

        compliance_flags = {
            "requires_csd": True,
            "requires_tax_clearance": True,
            "requires_bbee": True,
            "requires_sbd_forms": True,
        }

        payload = {
            "title": title,
            "reference_number": reference_number,
            "source_name": item.get("source_name"),
            "external_url": item.get("external_url"),
            "buyer_name": item.get("buyer_name"),
            "category": item.get("category"),
            "closing_date": item.get("closing_date"),
            "score": score,
            "pricing_summary": pricing_summary,
            "compliance_flags": compliance_flags,
            "status": "quote_ready",
        }

        results.append(payload)

    return results
