from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.domain.base import StrictBaseModel, utc_now
from app.harvest.source_tiers import HarvestTier


class ProcurementSourceRecord(StrictBaseModel):
    id: str
    name: str
    entity_type: str = ""
    source_tier: HarvestTier = HarvestTier.TIER_4
    base_url: str = ""
    harvest_url: str = ""
    parser_type: str = "html"
    province: str = ""
    is_active: bool = False
    requires_browser: bool = False
    requires_login: bool = False
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    failure_count: int = 0
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: Any = Field(default_factory=utc_now)
    updated_at: Any = Field(default_factory=utc_now)


class HarvestRunRecord(StrictBaseModel):
    run_id: str
    source_id: str = ""
    source_ids: List[str] = Field(default_factory=list)
    source_tier: Optional[HarvestTier] = None
    status: str = "queued"
    started_at: Any = Field(default_factory=utc_now)
    finished_at: Optional[datetime] = None
    source_count: int = 0
    opportunity_count: int = 0
    promoted_count: int = 0
    suppressed_count: int = 0
    warnings: List[str] = Field(default_factory=list)
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class TenderDocumentRecord(StrictBaseModel):
    title: str = ""
    document_url: str = ""
    source_url: str = ""
    document_type: str = ""
    checksum: str = ""
    notes: str = ""
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class TenderOpportunityRecord(StrictBaseModel):
    title: str = ""
    buyer: str = ""
    reference: str = ""
    closing_date: Optional[datetime] = None
    description: str = ""
    province: str = ""
    documents: List[TenderDocumentRecord] = Field(default_factory=list)
    source_url: str = ""
    briefing_required: Optional[bool] = None
    category_guess: str = ""
    qualification_status: str = ""
    qualification_score: float = 0.0
    recommendation: str = "MANUAL_REVIEW"
    promoted_for_review: bool = False
    suppressed_reason: str = ""
    possible_duplicate: bool = False
    duplicate_reasons: List[str] = Field(default_factory=list)
    low_confidence: bool = False
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: Any = Field(default_factory=utc_now)
    updated_at: Any = Field(default_factory=utc_now)


class SourceHealthRecord(StrictBaseModel):
    source_id: str
    status: str = "healthy"
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    failure_count: int = 0
    consecutive_failures: int = 0
    average_response_time: float = 0.0
    parser_failure_rate: float = 0.0
    attempt_count: int = 0
    parser_failure_count: int = 0
    disabled_reason: str = ""
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    updated_at: Any = Field(default_factory=utc_now)
