import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.services.supplier_quote_ingestion_service import SupplierQuoteIngestionService


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        text = str(value).strip()
        return text if text else default
    except Exception:
        return default


def _normalize_ref(value: Any) -> str:
    text = _safe_str(value).upper()
    text = re.sub(r"[^A-Z0-9]+", "", text)
    return text


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return round(float(value), 2)
    except Exception:
        return None


def _find_best_monthly_quote_folder(
    save_root: Path,
    rfq_number: Optional[str],
    quote_number: Optional[str],
) -> Optional[Path]:
    if not save_root.exists():
        return None

    target_rfq = _normalize_ref(rfq_number)
    target_quote = _normalize_ref(quote_number)

    candidate_folders: List[Path] = []
    for month_dir in sorted(save_root.glob("*"), reverse=True):
        if month_dir.is_dir():
            for child in sorted(month_dir.glob("*"), reverse=True):
                if child.is_dir():
                    candidate_folders.append(child)

    for folder in candidate_folders:
        folder_name_norm = _normalize_ref(folder.name)

        rfq_match = bool(target_rfq and target_rfq in folder_name_norm)
        quote_match = bool(target_quote and target_quote in folder_name_norm)

        if rfq_match or quote_match:
            return folder

        comparison_path = folder / "quote_comparison.json"
        if comparison_path.exists():
            payload = _load_json(comparison_path)
            json_rfq = _normalize_ref(payload.get("rfq_number"))
            json_quote = _normalize_ref(payload.get("lmcp_quote_number"))

            if (target_rfq and target_rfq == json_rfq) or (target_quote and target_quote == json_quote):
                return folder

    return None


def _collect_supplier_files(folder: Path) -> List[str]:
    files: List[str] = []
    for item in sorted(folder.glob("*")):
        if item.is_file() and item.name != "quote_comparison.json":
            files.append(str(item))
    return files


def _extract_path_strings(value: Any) -> List[str]:
    paths: List[str] = []

    if isinstance(value, str):
        text = value.strip()
        if text:
            paths.append(text)
        return paths

    if isinstance(value, list):
        for item in value:
            paths.extend(_extract_path_strings(item))
        return paths

    if isinstance(value, dict):
        for key in (
            "source",
            "copied_to",
            "file_path",
            "path",
            "stored_file",
        ):
            if key in value:
                paths.extend(_extract_path_strings(value.get(key)))
        return paths

    return paths


def _materialize_existing_paths(paths: Iterable[str]) -> List[Path]:
    found: List[Path] = []
    seen: set[str] = set()

    for raw_path in paths:
        candidate = Path(_safe_str(raw_path))
        if not candidate:
            continue
        try:
            resolved_key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        except Exception:
            resolved_key = str(candidate)
        if candidate.exists() and candidate.is_file() and resolved_key not in seen:
            found.append(candidate)
            seen.add(resolved_key)

    return found


def _infer_local_quote_roots(result: Dict[str, Any]) -> List[Path]:
    roots: List[Path] = []
    candidates: List[str] = []

    for key in (
        "quote_pack_json_path",
        "generated_json_path",
        "quote_pack_path",
        "manifest_path",
        "submission_package_manifest_path",
    ):
        candidates.extend(_extract_path_strings(result.get(key)))

    review_ready = _safe_dict(result.get("review_ready_bundle"))
    candidates.extend(_extract_path_strings(review_ready))

    for raw in candidates:
        path = Path(raw)
        parent = path.parent
        if not parent:
            continue
        roots.append(parent / "source_quotes")
        tender_id = _safe_str(result.get("tender_id") or result.get("rfq_number") or result.get("buyer_rfq_number"))
        if tender_id:
            roots.append(parent / f"{tender_id}__submission_package" / "source_quotes")

    unique: List[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            unique.append(root)
            seen.add(key)
    return unique


def _collect_supplier_files_from_result(result: Dict[str, Any], folder_files: List[str]) -> List[str]:
    collected: List[str] = list(folder_files)

    for key in ("source_quote_entries", "supplier_quote_files"):
        collected.extend(_extract_path_strings(result.get(key)))

    for key in ("harvest_enrichment", "live_rfq", "rfq", "submission_package_manifest"):
        collected.extend(_extract_path_strings(result.get(key)))

    harvest = _safe_dict(result.get("harvest_enrichment"))
    for key in ("supplier_quote_files", "supplierQuoteFiles", "supplier_quote_comparison", "supplierQuoteComparison", "live_rfq", "liveRfq"):
        collected.extend(_extract_path_strings(harvest.get(key)))

    materialized = _materialize_existing_paths(collected)

    by_name = {path.name for path in materialized}
    for root in _infer_local_quote_roots(result):
        if not root.exists() or not root.is_dir():
            continue
        for item in sorted(root.glob("*")):
            if item.is_file() and item.name not in by_name:
                materialized.append(item)
                by_name.add(item.name)

    return [str(path) for path in materialized]


def _supplier_name_from_path(path: str) -> str:
    name = Path(path).stem
    name = re.sub(r"[_-]+quote$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[_-]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name.title() if name else "Unknown Supplier"


def _collect_pricing_rows(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen: set[Tuple[Any, ...]] = set()
    candidates: List[Any] = [
        result.get("items"),
        result.get("line_items"),
        result.get("pricing_rows"),
        result.get("rows"),
        (_safe_dict(result.get("final_output"))).get("items"),
    ]

    pricing_result = _safe_dict(result.get("pricing_result"))
    candidates.extend([
        pricing_result.get("buyer_schedule"),
        pricing_result.get("priced_items"),
        pricing_result.get("items"),
    ])

    for candidate in candidates:
        if not isinstance(candidate, list):
            continue
        for item in candidate:
            if isinstance(item, dict):
                key = (
                    item.get("item_number"),
                    item.get("description"),
                    item.get("quantity"),
                    item.get("unit_price"),
                    item.get("line_total"),
                    item.get("supplier_name"),
                    item.get("supplier_quote_ref"),
                )
                if key in seen:
                    continue
                seen.add(key)
                rows.append(item)

    return rows


def _build_pricing_supplier_map(result: Dict[str, Any]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    supplier_map: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for row in _collect_pricing_rows(result):
        supplier_name = _safe_str(row.get("supplier_name"))
        quote_ref = _safe_str(row.get("supplier_quote_ref") or row.get("quote_reference"))
        if not supplier_name:
            continue

        key = (supplier_name.lower(), quote_ref.lower())
        line_total = _to_float(row.get("line_total"))
        if line_total is None:
            quantity = _to_float(row.get("quantity"))
            unit_price = _to_float(row.get("unit_price"))
            if quantity is not None and unit_price is not None:
                line_total = round(quantity * unit_price, 2)

        entry = supplier_map.setdefault(
            key,
            {
                "supplier_name": supplier_name,
                "quote_reference": quote_ref,
                "quoted_total": 0.0,
                "traceability_chain": [],
            },
        )
        if line_total is not None:
            entry["quoted_total"] = round(float(entry.get("quoted_total") or 0.0) + line_total, 2)
        entry["traceability_chain"].append(
            {
                "evidence_type": "pricing_payload",
                "item_number": row.get("item_number"),
                "description": row.get("description"),
                "line_total": line_total,
            }
        )

    return supplier_map


def _is_placeholder_recommendation(recommended: Dict[str, Any], result: Dict[str, Any]) -> bool:
    if not recommended:
        return True

    supplier_name = _safe_str(recommended.get("supplier_name"))
    quote_ref = _safe_str(recommended.get("quote_reference"))
    quoted_total = _to_float(recommended.get("quoted_total"))
    traceability = recommended.get("traceability_chain")

    expected_refs = {
        _normalize_ref(result.get("tender_id")),
        _normalize_ref(result.get("rfq_number")),
        _normalize_ref(result.get("buyer_rfq_number")),
        _normalize_ref(result.get("reference_number")),
    }
    supplier_norm = _normalize_ref(supplier_name)
    quote_norm = _normalize_ref(quote_ref)

    if quoted_total in (None, 0.0) and not traceability:
        return True
    if supplier_norm and supplier_norm in {value for value in expected_refs if value}:
        return True
    if quote_norm and quote_norm in {value for value in expected_refs if value} and quoted_total in (None, 0.0):
        return True
    return False


def _build_enriched_comparison(
    result: Dict[str, Any],
    comparison_payload: Dict[str, Any],
    supplier_files: List[str],
) -> Dict[str, Any]:
    supplier_quotes: List[Dict[str, Any]] = []
    index_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    pricing_map = _build_pricing_supplier_map(result)

    def upsert_supplier(entry: Dict[str, Any]) -> None:
        supplier_name = _safe_str(entry.get("supplier_name"))
        quote_ref = _safe_str(entry.get("quote_reference"))
        if not supplier_name:
            return

        key = (supplier_name.lower(), quote_ref.lower())
        fallback_keys = [key]
        if quote_ref:
            fallback_keys.append((supplier_name.lower(), ""))
        else:
            fallback_keys.extend([candidate for candidate in index_by_key if candidate[0] == supplier_name.lower()])

        existing = next((index_by_key.get(candidate) for candidate in fallback_keys if index_by_key.get(candidate)), None)
        if not existing:
            clean_entry = {
                "supplier_name": supplier_name,
                "quote_reference": quote_ref,
                "quoted_total": _to_float(entry.get("quoted_total")),
                "source_file": _safe_str(entry.get("source_file")),
                "traceability_chain": _safe_list(entry.get("traceability_chain")),
            }
            supplier_quotes.append(clean_entry)
            index_by_key[key] = clean_entry
            existing = clean_entry
        elif quote_ref and not _safe_str(existing.get("quote_reference")):
            existing["quote_reference"] = quote_ref
            index_by_key[key] = existing

        quoted_total = _to_float(entry.get("quoted_total"))
        if quoted_total is not None:
            existing["quoted_total"] = quoted_total
        source_file = _safe_str(entry.get("source_file"))
        if source_file and not existing.get("source_file"):
            existing["source_file"] = source_file
        traceability = _safe_list(entry.get("traceability_chain"))
        if traceability:
            existing_chain = _safe_list(existing.get("traceability_chain"))
            for trace in traceability:
                if trace not in existing_chain:
                    existing_chain.append(trace)
            existing["traceability_chain"] = existing_chain

    for quote in _safe_list(comparison_payload.get("supplier_quotes")):
        if not isinstance(quote, dict):
            continue
        upsert_supplier(quote)

    for supplier_file in supplier_files:
        supplier_name = _supplier_name_from_path(supplier_file)
        traceability_chain = [{"evidence_type": "supplier_quote_file", "file_path": supplier_file}]
        pricing_entry = pricing_map.get((supplier_name.lower(), ""))
        upsert_supplier(
            {
                "supplier_name": supplier_name,
                "quote_reference": _safe_str((pricing_entry or {}).get("quote_reference")),
                "quoted_total": (pricing_entry or {}).get("quoted_total"),
                "source_file": supplier_file,
                "traceability_chain": traceability_chain + _safe_list((pricing_entry or {}).get("traceability_chain")),
            }
        )

    for pricing_entry in pricing_map.values():
        upsert_supplier(pricing_entry)

    supplier_quotes.sort(
        key=lambda item: (
            item.get("quoted_total") is None,
            item.get("quoted_total") if item.get("quoted_total") is not None else float("inf"),
            _safe_str(item.get("supplier_name")).lower(),
        )
    )

    valid_recommended = _safe_dict(comparison_payload.get("recommended_supplier"))
    if _is_placeholder_recommendation(valid_recommended, result):
        valid_recommended = {}

    recommended_supplier = {}
    if valid_recommended:
        key = (
            _safe_str(valid_recommended.get("supplier_name")).lower(),
            _safe_str(valid_recommended.get("quote_reference")).lower(),
        )
        recommended_supplier = deepcopy(index_by_key.get(key) or valid_recommended)
    elif supplier_quotes:
        preferred = next((quote for quote in supplier_quotes if quote.get("quoted_total") is not None), supplier_quotes[0])
        recommended_supplier = deepcopy(preferred)

    runner_up_supplier = {}
    for quote in supplier_quotes:
        if recommended_supplier and (
            _safe_str(quote.get("supplier_name")).lower(),
            _safe_str(quote.get("quote_reference")).lower(),
        ) == (
            _safe_str(recommended_supplier.get("supplier_name")).lower(),
            _safe_str(recommended_supplier.get("quote_reference")).lower(),
        ):
            continue
        runner_up_supplier = deepcopy(quote)
        break

    estimated_savings = None
    recommended_total = _to_float(recommended_supplier.get("quoted_total"))
    runner_up_total = _to_float(runner_up_supplier.get("quoted_total"))
    if recommended_total is not None and runner_up_total is not None:
        estimated_savings = round(runner_up_total - recommended_total, 2)

    if not supplier_quotes:
        comparison_status = "missing_supplier_quotes"
    elif recommended_supplier and recommended_total is not None:
        comparison_status = "ready" if (not runner_up_supplier or runner_up_total is not None) else "partial_evidence"
    else:
        comparison_status = "partial_evidence"

    return {
        "comparison_status": comparison_status,
        "comparison_ready": bool(supplier_quotes),
        "supplier_quotes": supplier_quotes,
        "recommended_supplier": recommended_supplier,
        "runner_up_supplier": runner_up_supplier,
        "estimated_savings_vs_runner_up": estimated_savings,
    }


def attach_supplier_quotes_to_result(result: Dict[str, Any]) -> Dict[str, Any]:
    output = deepcopy(result)

    save_root = Path(os.getenv("SUPPLIER_QUOTES_SAVE_ROOT", "monthly_quotes"))
    comparison_payload = deepcopy(_safe_dict(output.get("supplier_quote_comparison")))

    rfq = (
        output.get("buyer_rfq_number")
        or output.get("rfq_number")
        or (output.get("rfq") or {}).get("buyer_rfq_number")
        or (output.get("rfq") or {}).get("rfq_number")
        or output.get("reference_number")
    )

    quote_number = (
        output.get("quote_number")
        or output.get("document_number")
        or (output.get("submission_pack") or {}).get("quote_number")
    )

    folder = _find_best_monthly_quote_folder(
        save_root=save_root,
        rfq_number=rfq,
        quote_number=quote_number,
    )

    comparison_path = folder / "quote_comparison.json" if folder else None
    if comparison_path and comparison_path.exists():
        comparison_payload.update(_load_json(comparison_path))
    files = _collect_supplier_files(folder) if folder else []
    files = _collect_supplier_files_from_result(output, files)
    comparison_payload = _build_enriched_comparison(output, comparison_payload, files)

    output["supplier_quotes_found"] = bool(files or comparison_payload.get("supplier_quotes"))
    output["supplier_quotes_folder"] = str(folder) if folder else (str(Path(files[0]).parent) if files else None)
    output["supplier_quote_files"] = files
    output["supplier_quote_comparison"] = comparison_payload
    output["supplier_quotes_count"] = len(comparison_payload.get("supplier_quotes") or [])
    output["supplier_responses_count"] = len(comparison_payload.get("supplier_quotes") or [])

    return output


def ingest_and_attach_supplier_quotes(result: Dict[str, Any]) -> Dict[str, Any]:
    output = deepcopy(result)

    try:
        ingestion_result = SupplierQuoteIngestionService().ingest_once()
    except Exception as exc:
        ingestion_result = {
            "success": False,
            "processed": 0,
            "saved_attachments": 0,
            "folders_updated": [],
            "errors": [str(exc)],
        }

    output["supplier_ingestion"] = ingestion_result
    output = attach_supplier_quotes_to_result(output)
    return output


def attach_supplier_quotes_batch(
    results: List[Dict[str, Any]],
    supplier_ingestion_result: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []

    for item in results:
        if not isinstance(item, dict):
            enriched.append(item)
            continue

        result = deepcopy(item)
        if supplier_ingestion_result is not None:
            result["supplier_ingestion"] = supplier_ingestion_result
        result = attach_supplier_quotes_to_result(result)
        enriched.append(result)

    return enriched
