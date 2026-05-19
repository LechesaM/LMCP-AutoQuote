from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from datetime import datetime
from html import unescape
from typing import Any, Dict, Iterable, List
from urllib.parse import urljoin, urlparse


def _clean_text(value: str) -> str:
    return " ".join(unescape(str(value or "")).split())


def _extract_links(html: str, base_url: str = "") -> List[str]:
    links = re.findall(r'href=["\']([^"\']+)["\']', html or "", flags=re.I)
    output: List[str] = []
    for link in links:
        url = urljoin(base_url, link)
        if url:
            output.append(url)
    return output


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    for candidate in (text, text.replace("/", "-"), text.replace(".", "-")):
        try:
            return datetime.fromisoformat(candidate)
        except Exception:
            continue
    match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if match:
        try:
            return datetime.fromisoformat(match.group(1))
        except Exception:
            return None
    return None


def _base_output(source_payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": "",
        "buyer": "",
        "reference": "",
        "closing_date": None,
        "description": "",
        "province": None,
        "documents": [],
        "source_url": str(source_payload.get("source_url") or source_payload.get("url") or ""),
        "briefing_required": None,
        "category_guess": None,
    }


class BaseParser(ABC):
    parser_name = "base"

    @abstractmethod
    def parse(self, source_payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class HtmlTenderParser(BaseParser):
    parser_name = "html"

    def parse(self, source_payload: Dict[str, Any]) -> Dict[str, Any]:
        html = str(source_payload.get("html") or source_payload.get("text") or "")
        text = _clean_text(re.sub(r"<[^>]+>", " ", html))
        output = _base_output(source_payload)
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.I | re.S)
        if title_match:
            output["title"] = _clean_text(title_match.group(1))
        elif h1_match:
            output["title"] = _clean_text(h1_match.group(1))
        else:
            output["title"] = _clean_text(text[:120])
        buyer_match = re.search(r"(?:buyer|department|entity)\s*[:\-]\s*([^<\n]+)", text, flags=re.I)
        reference_match = re.search(r"(?:rfq|tender)\s*(?:no|number|ref)?\s*[:\-#]?\s*([A-Z0-9/\-_.]+)", text, flags=re.I)
        output["buyer"] = _clean_text(buyer_match.group(1)) if buyer_match else str(source_payload.get("buyer") or "")
        output["reference"] = _clean_text(reference_match.group(1)) if reference_match else str(source_payload.get("reference") or "")
        output["description"] = text[:4000]
        output["province"] = source_payload.get("province") or None
        output["documents"] = [{"document_url": url, "title": urlparse(url).path.rsplit("/", 1)[-1]} for url in _extract_links(html, output["source_url"]) if url]
        output["briefing_required"] = bool(re.search(r"compulsory briefing|mandatory site inspection|site inspection", text, flags=re.I))
        if "technical" in text.lower() or "fabrication" in text.lower():
            output["category_guess"] = "technical_fabrication"
        elif "building material" in text.lower():
            output["category_guess"] = "building_materials"
        elif "household" in text.lower():
            output["category_guess"] = "household_products"
        elif "equipment" in text.lower():
            output["category_guess"] = "equipment_supply"
        output["closing_date"] = _parse_date(source_payload.get("closing_date"))
        return output


class PdfListingParser(BaseParser):
    parser_name = "pdf"

    def parse(self, source_payload: Dict[str, Any]) -> Dict[str, Any]:
        text = _clean_text(source_payload.get("text") or source_payload.get("pdf_text") or "")
        output = _base_output(source_payload)
        output["title"] = _clean_text(source_payload.get("title") or text[:120])
        output["buyer"] = _clean_text(source_payload.get("buyer") or "")
        output["reference"] = _clean_text(source_payload.get("reference") or "")
        output["description"] = text[:4000]
        output["documents"] = list(source_payload.get("documents") or [])
        output["briefing_required"] = bool(re.search(r"compulsory briefing|mandatory site inspection", text, flags=re.I))
        output["category_guess"] = source_payload.get("category_guess") or None
        output["closing_date"] = _parse_date(source_payload.get("closing_date"))
        return output


class JsonApiParser(BaseParser):
    parser_name = "json"

    def parse(self, source_payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = source_payload.get("json") or source_payload.get("data") or source_payload
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        if not isinstance(payload, dict):
            payload = {}
        output = _base_output(source_payload)
        output["title"] = str(payload.get("title") or payload.get("name") or "")
        output["buyer"] = str(payload.get("buyer") or payload.get("entity") or "")
        output["reference"] = str(payload.get("reference") or payload.get("tender_number") or "")
        output["closing_date"] = _parse_date(payload.get("closing_date"))
        output["description"] = str(payload.get("description") or payload.get("summary") or "")
        output["province"] = payload.get("province") or None
        output["documents"] = list(payload.get("documents") or [])
        output["briefing_required"] = payload.get("briefing_required")
        output["category_guess"] = payload.get("category_guess")
        return output


class EtendersParser(HtmlTenderParser):
    parser_name = "etenders"


class GenericTableParser(HtmlTenderParser):
    parser_name = "generic_table"


PARSER_MAP = {
    "html": HtmlTenderParser,
    "pdf": PdfListingParser,
    "json": JsonApiParser,
    "etenders": EtendersParser,
    "generic_table": GenericTableParser,
}
