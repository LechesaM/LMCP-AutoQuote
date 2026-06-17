from __future__ import annotations

from typing import Any, Callable, Dict, List

from app.services.document_ingestion_service import (
    extract_tender_candidates_from_html,
    normalize_document_record,
)
from app.services.source_parser_routing_service import route_source_parser


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


class ParserExecutorService:
    def __init__(self) -> None:
        self._parsers: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = {
            "parse_ocds_api": self.parse_ocds_api,
            "parse_generic_html_tenders": self.parse_generic_html_tenders,
            "parse_document_links": self.parse_document_links,
        }

    def execute(self, source: Dict[str, Any], harvested_payload: Dict[str, Any]) -> Dict[str, Any]:
        parser_name = route_source_parser(source)
        parser = self._parsers.get(parser_name, self.parse_generic_html_tenders)
        return parser(source, harvested_payload)

    def parse_ocds_api(self, source: Dict[str, Any], harvested_payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = harvested_payload.get("payload")
        releases: List[Dict[str, Any]] = []

        if isinstance(payload, dict):
            if isinstance(payload.get("releases"), list):
                releases = payload["releases"]
            elif isinstance(payload.get("data"), list):
                releases = payload["data"]

        results: List[Dict[str, Any]] = []

        for item in releases:
            ocid = _safe_str(item.get("ocid"))
            tender = item.get("tender") or {}
            buyer = item.get("buyer") or {}
            title = _safe_str(tender.get("title")) or _safe_str(item.get("title"))
            description = _safe_str(tender.get("description")) or _safe_str(item.get("description"))
            closing_date = _safe_str(tender.get("tenderPeriod", {}).get("endDate"))
            published_date = _safe_str(item.get("date"))
            buyer_name = _safe_str(buyer.get("name"))

            if not title and not description:
                continue

            results.append(
                {
                    "source_key": source.get("source_key", ""),
                    "entity_name": source.get("entity_name", ""),
                    "owner_type": source.get("owner_type", ""),
                    "entity_type": source.get("entity_type", ""),
                    "province": source.get("province", ""),
                    "rfq_number": ocid,
                    "title": title,
                    "description": description,
                    "buyer_name": buyer_name,
                    "closing_date": closing_date,
                    "published_date": published_date,
                    "source_url": source.get("base_url", ""),
                    "source_type": "ocds_api",
                    "document_type": "ocds_release",
                }
            )

        return {
            "status": "success",
            "parser": "parse_ocds_api",
            "count": len(results),
            "results": results,
        }

    def parse_generic_html_tenders(self, source: Dict[str, Any], harvested_payload: Dict[str, Any]) -> Dict[str, Any]:
        html = _safe_str(harvested_payload.get("text"))
        candidates = extract_tender_candidates_from_html(html, source_url=_safe_str(source.get("base_url")))

        results: List[Dict[str, Any]] = []
        for item in candidates:
            normalized = normalize_document_record(item)
            results.append(
                {
                    "source_key": source.get("source_key", ""),
                    "entity_name": source.get("entity_name", ""),
                    "owner_type": source.get("owner_type", ""),
                    "entity_type": source.get("entity_type", ""),
                    "province": source.get("province", ""),
                    "rfq_number": "",
                    "title": normalized["title"],
                    "description": normalized["description"],
                    "buyer_name": source.get("entity_name", ""),
                    "closing_date": "",
                    "published_date": "",
                    "source_url": normalized["source_url"] or source.get("base_url", ""),
                    "source_type": "website",
                    "document_type": normalized["document_type"],
                }
            )

        return {
            "status": "success",
            "parser": "parse_generic_html_tenders",
            "count": len(results),
            "results": results,
        }

    def parse_document_links(self, source: Dict[str, Any], harvested_payload: Dict[str, Any]) -> Dict[str, Any]:
        url = _safe_str(source.get("base_url"))
        result = {
            "source_key": source.get("source_key", ""),
            "entity_name": source.get("entity_name", ""),
            "owner_type": source.get("owner_type", ""),
            "entity_type": source.get("entity_type", ""),
            "province": source.get("province", ""),
            "rfq_number": "",
            "title": harvested_payload.get("filename") or "Tender document",
            "description": harvested_payload.get("filename") or url,
            "buyer_name": source.get("entity_name", ""),
            "closing_date": "",
            "published_date": "",
            "source_url": url,
            "source_type": "document",
            "document_type": "linked_document",
        }

        return {
            "status": "success",
            "parser": "parse_document_links",
            "count": 1 if url else 0,
            "results": [result] if url else [],
        }


parser_executor_service = ParserExecutorService()
