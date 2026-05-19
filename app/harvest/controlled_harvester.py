from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Sequence
from uuid import uuid4

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None  # type: ignore

from app.core.runtime_paths import get_runtime_paths
from app.harvest.deduplication import annotate_possible_duplicates, find_possible_duplicates
from app.harvest.filtering import evaluate_prequalification
from app.harvest.operator_capacity import OperatorCapacityConfig
from app.harvest.parsers import PARSER_MAP, BaseParser
from app.harvest.promotion_policy import prioritize_promotions
from app.harvest.source_health import record_failure, record_success
from app.harvest.source_models import HarvestRunRecord, TenderDocumentRecord, TenderOpportunityRecord
from app.harvest.source_registry import SourceRegistry, load_source_registry
from app.harvest.source_tiers import HarvestTier, is_passive_tier
from app.qualification.qualification_engine import qualify_rfq


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _jsonl_path(filename: str) -> Path:
    return get_runtime_paths().manual_production_file(filename)


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    output: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            output.append(payload)
    return output


def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _parser_for_type(parser_type: str) -> BaseParser:
    parser_cls = PARSER_MAP.get(str(parser_type or "").lower(), PARSER_MAP["html"])
    return parser_cls()


def _build_documents(documents: Sequence[Dict[str, Any] | str] | None, source_url: str) -> List[TenderDocumentRecord]:
    output: List[TenderDocumentRecord] = []
    for document in documents or []:
        if isinstance(document, str):
            output.append(TenderDocumentRecord(document_url=document, source_url=source_url, title=document.rsplit("/", 1)[-1]))
            continue
        payload = dict(document or {})
        output.append(
            TenderDocumentRecord(
                title=str(payload.get("title") or payload.get("name") or payload.get("document_url") or ""),
                document_url=str(payload.get("document_url") or payload.get("url") or ""),
                source_url=str(payload.get("source_url") or source_url),
                document_type=str(payload.get("document_type") or payload.get("type") or ""),
                checksum=str(payload.get("checksum") or ""),
                notes=str(payload.get("notes") or ""),
                metadata_json={k: v for k, v in payload.items() if k not in {"title", "name", "document_url", "url", "source_url", "document_type", "type", "checksum", "notes"}},
            )
        )
    return output


class ControlledHarvester:
    def __init__(
        self,
        registry: SourceRegistry | None = None,
        *,
        capacity_config: OperatorCapacityConfig | None = None,
        fetcher: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]] | None = None,
    ) -> None:
        self.registry = registry or load_source_registry()
        self.capacity_config = capacity_config or OperatorCapacityConfig()
        self.fetcher = fetcher or self._default_fetcher

    async def _default_fetcher(self, source: Dict[str, Any]) -> Dict[str, Any]:
        url = str(source.get("harvest_url") or source.get("base_url") or "")
        if not url:
            raise ValueError("source has no harvest URL")
        if url.startswith("file://"):
            file_path = Path(url.replace("file://", "", 1))
            content = file_path.read_text(encoding="utf-8")
            return {"source_url": url, "html": content, "text": content, "content_type": "text/html", "status_code": 200}
        if httpx is None:
            raise RuntimeError("httpx is not available in this environment")
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "LMCP-Harvester/1.0"})
            content_type = response.headers.get("content-type", "")
            payload: Dict[str, Any] = {
                "source_url": url,
                "url": url,
                "content_type": content_type,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "raw_content": response.content,
            }
            if "application/json" in content_type.lower():
                try:
                    payload["json"] = response.json()
                except Exception:
                    payload["text"] = response.text
            else:
                payload["html"] = response.text
                payload["text"] = response.text
            return payload

    def _runs_path(self) -> Path:
        return _jsonl_path("harvest_runs.jsonl")

    def _opportunities_path(self) -> Path:
        return _jsonl_path("harvest_opportunities.jsonl")

    def _load_opportunities(self) -> List[Dict[str, Any]]:
        return _read_jsonl(self._opportunities_path())

    def _promoted_count(self) -> int:
        return sum(1 for item in self._load_opportunities() if bool(item.get("promoted_for_review")))

    def _store_run(self, record: HarvestRunRecord) -> None:
        _append_jsonl(self._runs_path(), record.to_jsonable_dict())

    def _store_opportunity(self, record: TenderOpportunityRecord) -> None:
        _append_jsonl(self._opportunities_path(), record.to_jsonable_dict())

    def list_runs(self, limit: int = 200) -> List[Dict[str, Any]]:
        return _read_jsonl(self._runs_path())[-max(1, int(limit)) :]

    def list_opportunities(self, limit: int = 200) -> List[Dict[str, Any]]:
        return _read_jsonl(self._opportunities_path())[-max(1, int(limit)) :]

    async def harvest_source(self, source_id: str) -> Dict[str, Any]:
        source = next((item for item in self.registry.list_sources() if item.id == str(source_id)), None)
        if not source:
            raise KeyError(f"Unknown source id: {source_id}")
        source_payload = source.to_jsonable_dict()
        source_tier = HarvestTier.from_value(source.source_tier)
        run = HarvestRunRecord.validate_payload({
            "run_id": f"harvest-{uuid4().hex}",
            "source_id": source.id,
            "source_ids": [source.id],
            "source_tier": source_tier,
            "status": "running",
            "started_at": _now(),
            "metadata_json": {"source_name": source.name, "source_tier": source_tier.value},
        })
        if is_passive_tier(source_tier):
            run = run.model_copy(update={"status": "skipped", "finished_at": _now(), "warnings": ["tier 4 passive source not harvested directly"]})
            self._store_run(run)
            return {"run": run.to_jsonable_dict(), "opportunities": [], "skipped": True, "reason": "tier 4 passive source"}

        started = _now()
        try:
            fetched = await self.fetcher(source_payload)
            parser = _parser_for_type(source.parser_type)
            parsed = parser.parse(fetched | {"source_url": fetched.get("source_url") or source.harvest_url or source.base_url})
            documents = _build_documents(parsed.get("documents"), parsed.get("source_url") or source.harvest_url or source.base_url)
            opportunity_payload: Dict[str, Any] = {
                **parsed,
                "documents": [doc.to_jsonable_dict() for doc in documents],
                "source_url": parsed.get("source_url") or source.harvest_url or source.base_url,
                "source_tier": source_tier.value,
                "raw_payload": fetched,
            }
            prequalification = evaluate_prequalification(opportunity_payload)
            qualification_input = dict(opportunity_payload)
            qualification_input["low_confidence"] = bool(prequalification.get("low_confidence"))
            qualification_input["estimated_profit"] = prequalification.get("estimated_profit")
            qualification_input["qualification_hint"] = prequalification.get("qualification_hint")
            qualified = qualify_rfq(qualification_input)
            opportunity = TenderOpportunityRecord.validate_payload({
                "title": opportunity_payload.get("title") or source.name,
                "buyer": opportunity_payload.get("buyer") or source.entity_type,
                "reference": opportunity_payload.get("reference") or source.id,
                "closing_date": opportunity_payload.get("closing_date"),
                "description": opportunity_payload.get("description") or "",
                "province": opportunity_payload.get("province") or source.province,
                "documents": opportunity_payload.get("documents") or [],
                "source_url": opportunity_payload.get("source_url") or source.harvest_url or source.base_url,
                "briefing_required": opportunity_payload.get("briefing_required"),
                "category_guess": opportunity_payload.get("category_guess") or qualified.get("category"),
                "qualification_status": qualified.get("recommendation", "MANUAL_REVIEW"),
                "qualification_score": float(qualified.get("automation_suitability_score") or 0.0),
                "recommendation": qualified.get("recommendation", "MANUAL_REVIEW"),
                "promoted_for_review": False,
                "suppressed_reason": prequalification.get("rejection_reason") or "",
                "possible_duplicate": bool(find_possible_duplicates(opportunity_payload, self._load_opportunities())),
                "duplicate_reasons": find_possible_duplicates(opportunity_payload, self._load_opportunities()),
                "low_confidence": bool(prequalification.get("low_confidence")),
                "raw_payload": fetched,
            })
            promotion_summary = prioritize_promotions(
                [
                    {
                        **opportunity.to_jsonable_dict(),
                        **qualified,
                        "source_tier": source_tier.value,
                        "qualification_score": opportunity.qualification_score,
                        "supplier_evidence_score": qualified.get("supplier_evidence_score", 0.0),
                        "source_url": opportunity.source_url,
                    }
                ],
                already_promoted_count=self._promoted_count(),
                capacity_config=self.capacity_config,
            )
            promoted = bool(promotion_summary["promoted"])
            suppression_reason = ""
            if promoted:
                opportunity = opportunity.model_copy(update={"promoted_for_review": True, "suppressed_reason": ""})
            else:
                suppression_reason = str(promotion_summary["suppressed"][0].get("suppression_reason") if promotion_summary["suppressed"] else prequalification.get("rejection_reason") or "")
                opportunity = opportunity.model_copy(update={"promoted_for_review": False, "suppressed_reason": suppression_reason})
            self._store_opportunity(opportunity)
            run = run.model_copy(update={
                "status": "completed",
                "finished_at": _now(),
                "source_count": 1,
                "opportunity_count": 1,
                "promoted_count": 1 if promoted else 0,
                "suppressed_count": 0 if promoted else 1,
                "warnings": list(dict.fromkeys([
                    *prequalification.get("reasons", []),
                    *(qualified.get("warnings", []) if isinstance(qualified.get("warnings"), list) else []),
                ])),
                "metadata_json": {
                    "source_name": source.name,
                    "source_tier": source_tier.value,
                    "promotion_summary": promotion_summary,
                    "qualification_recommendation": qualified.get("recommendation"),
                },
            })
            self._store_run(run)
            record_success(source.id, response_time_seconds=max(0.0, (_now() - started).total_seconds()), parser_failure=False, metadata={"harvest": "success"})
            return {
                "run": run.to_jsonable_dict(),
                "opportunities": [opportunity.to_jsonable_dict()],
                "qualification": qualified,
                "promotion_summary": promotion_summary,
                "prequalification": prequalification,
            }
        except Exception as exc:
            run = run.model_copy(update={"status": "failed", "finished_at": _now(), "warnings": [str(exc)]})
            self._store_run(run)
            record_failure(source.id, parser_failure=True, metadata={"error": str(exc)})
            raise

    async def harvest_tier(self, tier: str | HarvestTier) -> Dict[str, Any]:
        resolved = HarvestTier.from_value(tier)
        if is_passive_tier(resolved):
            run = HarvestRunRecord.validate_payload({
                "run_id": f"harvest-{uuid4().hex}",
                "source_tier": resolved,
                "status": "skipped",
                "started_at": _now(),
                "finished_at": _now(),
                "warnings": ["tier 4 passive sources are discovery only"],
            })
            self._store_run(run)
            return {"run": run.to_jsonable_dict(), "opportunities": [], "skipped": True}
        sources = [source for source in self.registry.list_sources_by_tier(resolved) if source.is_active]
        results: List[Dict[str, Any]] = []
        for source in sources:
            results.append(await self.harvest_source(source.id))
        return {"tier": resolved.value, "results": results}

    async def harvest_selected_sources(self, source_ids: Iterable[str]) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        for source_id in source_ids:
            results.append(await self.harvest_source(source_id))
        return {"results": results}

    async def harvest_all_active_sources(self, max_sources: int | None = None) -> Dict[str, Any]:
        limit = 25 if max_sources is None else max(1, int(max_sources))
        active_sources = [source for source in self.registry.list_active_sources() if not is_passive_tier(source.source_tier)]
        results: List[Dict[str, Any]] = []
        for source in active_sources[:limit]:
            results.append(await self.harvest_source(source.id))
        return {"results": results, "processed_count": len(results), "max_sources": limit}
