import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def attach_supplier_quotes_to_result(result: Dict[str, Any]) -> Dict[str, Any]:
    output = deepcopy(result)

    save_root = Path(os.getenv("SUPPLIER_QUOTES_SAVE_ROOT", "monthly_quotes"))

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

    if not folder:
        output["supplier_quotes_found"] = False
        output["supplier_quotes_folder"] = None
        output["supplier_quote_files"] = []
        output["supplier_quote_comparison"] = {}
        output["supplier_quotes_count"] = 0
        output["supplier_responses_count"] = 0
        return output

    comparison_path = folder / "quote_comparison.json"
    comparison_payload = _load_json(comparison_path) if comparison_path.exists() else {}
    files = _collect_supplier_files(folder)

    output["supplier_quotes_found"] = True
    output["supplier_quotes_folder"] = str(folder)
    output["supplier_quote_files"] = files
    output["supplier_quote_comparison"] = comparison_payload
    output["supplier_quotes_count"] = len(files)

    suppliers = comparison_payload.get("suppliers", [])
    output["supplier_responses_count"] = len(suppliers) if isinstance(suppliers, list) else 0

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
