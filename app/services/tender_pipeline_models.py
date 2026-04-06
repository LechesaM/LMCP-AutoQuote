from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class SubmissionMethod(str, Enum):
    EMAIL = "email"
    PORTAL = "portal"
    PHYSICAL = "physical"
    COURIER = "courier"
    UNKNOWN = "unknown"


class BriefingRequirement(str, Enum):
    NONE = "none"
    OPTIONAL = "optional"
    COMPULSORY = "compulsory"
    UNKNOWN = "unknown"


class TenderStatus(str, Enum):
    HARVESTED = "harvested"
    NORMALIZED = "normalized"
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    MANUAL_REVIEW = "manual_review"
    QUOTE_GENERATED = "quote_generated"
    PACK_GENERATED = "pack_generated"
    FAILED = "failed"


class EligibilityDecision(str, Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    MANUAL_REVIEW = "manual_review"


class DocumentType(str, Enum):
    TENDER_NOTICE = "tender_notice"
    BOQ = "boq"
    SCOPE = "scope"
    DRAWING = "drawing"
    SBD = "sbd"
    TERMS = "terms"
    PRICING_SCHEDULE = "pricing_schedule"
    OTHER = "other"


class ContactDetails(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None


class TenderDocument(BaseModel):
    name: str
    url: Optional[str] = None
    document_type: DocumentType = DocumentType.OTHER
    file_name: Optional[str] = None
    file_extension: Optional[str] = None
    local_path: Optional[str] = None
    size_bytes: Optional[int] = None


class TenderFlags(BaseModel):
    email_submission_allowed: bool = False
    portal_submission_allowed: bool = False
    physical_submission_required: bool = False
    courier_submission_required: bool = False

    compulsory_briefing: bool = False
    optional_briefing: bool = False
    unclear_briefing: bool = False

    has_pricing_schedule: bool = False
    has_boq: bool = False
    has_sbd_forms: bool = False
    has_scope_of_work: bool = False

    deadline_found: bool = False
    contact_found: bool = False
    submission_method_clear: bool = False
    requires_manual_review: bool = False


class TenderScoring(BaseModel):
    score: float = 0.0
    priority_band: str = "unscored"
    sector_fit: Optional[str] = None
    estimated_value_band: Optional[str] = None
    reasoning: List[str] = Field(default_factory=list)


class EligibilityResult(BaseModel):
    decision: EligibilityDecision = EligibilityDecision.MANUAL_REVIEW
    reasons: List[str] = Field(default_factory=list)
    passed_checks: List[str] = Field(default_factory=list)
    failed_checks: List[str] = Field(default_factory=list)


class QuotePackArtifact(BaseModel):
    artifact_type: str
    file_name: str
    local_path: Optional[str] = None
    generated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RawTenderInput(BaseModel):
    """
    Raw tender payload from harvester before normalization.
    This accepts flexible data because upstream sources may vary widely.
    """

    source: str
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    harvested_at: datetime = Field(default_factory=datetime.utcnow)
    payload: Dict[str, Any] = Field(default_factory=dict)


class NormalizedTender(BaseModel):
    """
    This is the single clean structure the rest of the system should use.
    Everything harvested must end up here before filtering, scoring,
    BOQ generation, SBD generation, or PDF pack creation.
    """

    # Identity
    tender_id: str
    reference_number: Optional[str] = None
    title: str
    issuing_entity: str

    # Source
    source: str
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    notice_url: Optional[str] = None

    # Dates
    harvested_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None
    closing_at: Optional[datetime] = None
    compulsory_briefing_at: Optional[datetime] = None
    optional_briefing_at: Optional[datetime] = None

    # Submission
    submission_method: SubmissionMethod = SubmissionMethod.UNKNOWN
    portal_name: Optional[str] = None
    portal_url: Optional[str] = None
    submission_email: Optional[str] = None
    submission_address: Optional[str] = None

    # Briefing
    briefing_requirement: BriefingRequirement = BriefingRequirement.UNKNOWN
    briefing_location: Optional[str] = None

    # Content
    description: Optional[str] = None
    scope_summary: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    region: Optional[str] = None
    province: Optional[str] = None
    municipality: Optional[str] = None

    # Financial / strategic hints
    estimated_value: Optional[float] = None
    currency: str = "ZAR"
    cidb_grading: Optional[str] = None

    # Contacts / docs
    contact_details: List[ContactDetails] = Field(default_factory=list)
    documents: List[TenderDocument] = Field(default_factory=list)

    # Operational fields
    status: TenderStatus = TenderStatus.HARVESTED
    flags: TenderFlags = Field(default_factory=TenderFlags)
    scoring: TenderScoring = Field(default_factory=TenderScoring)
    eligibility: EligibilityResult = Field(default_factory=EligibilityResult)
    tags: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

    # Quote / pack outputs
    generated_artifacts: List[QuotePackArtifact] = Field(default_factory=list)

    # Full raw content for traceability
    raw_text: Optional[str] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "issuing_entity", "source")
    @classmethod
    def validate_required_strings(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("Field may not be blank.")
        return str(value).strip()

    @field_validator("reference_number", "submission_email", "submission_address", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def sync_flags_from_submission_and_briefing(self) -> "NormalizedTender":
        # Submission flags
        self.flags.email_submission_allowed = self.submission_method == SubmissionMethod.EMAIL
        self.flags.portal_submission_allowed = self.submission_method == SubmissionMethod.PORTAL
        self.flags.physical_submission_required = self.submission_method == SubmissionMethod.PHYSICAL
        self.flags.courier_submission_required = self.submission_method == SubmissionMethod.COURIER
        self.flags.submission_method_clear = self.submission_method != SubmissionMethod.UNKNOWN

        # Briefing flags
        self.flags.compulsory_briefing = self.briefing_requirement == BriefingRequirement.COMPULSORY
        self.flags.optional_briefing = self.briefing_requirement == BriefingRequirement.OPTIONAL
        self.flags.unclear_briefing = self.briefing_requirement == BriefingRequirement.UNKNOWN

        # Docs flags
        doc_types = {doc.document_type for doc in self.documents}
        self.flags.has_boq = DocumentType.BOQ in doc_types or DocumentType.PRICING_SCHEDULE in doc_types
        self.flags.has_pricing_schedule = DocumentType.PRICING_SCHEDULE in doc_types
        self.flags.has_sbd_forms = DocumentType.SBD in doc_types
        self.flags.has_scope_of_work = DocumentType.SCOPE in doc_types

        # General flags
        self.flags.deadline_found = self.closing_at is not None
        self.flags.contact_found = len(self.contact_details) > 0

        return self

    @property
    def is_email_only(self) -> bool:
        return (
            self.submission_method == SubmissionMethod.EMAIL
            and not self.flags.portal_submission_allowed
            and not self.flags.physical_submission_required
            and not self.flags.courier_submission_required
        )

    @property
    def is_portal_only(self) -> bool:
        return (
            self.submission_method == SubmissionMethod.PORTAL
            and not self.flags.email_submission_allowed
            and not self.flags.physical_submission_required
            and not self.flags.courier_submission_required
        )

    @property
    def has_compulsory_briefing(self) -> bool:
        return self.briefing_requirement == BriefingRequirement.COMPULSORY

    def add_note(self, note: str) -> None:
        if note and note.strip():
            self.notes.append(note.strip())

    def add_tag(self, tag: str) -> None:
        if tag and tag.strip():
            clean_tag = tag.strip().lower()
            if clean_tag not in self.tags:
                self.tags.append(clean_tag)

    def add_artifact(
        self,
        artifact_type: str,
        file_name: str,
        local_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.generated_artifacts.append(
            QuotePackArtifact(
                artifact_type=artifact_type,
                file_name=file_name,
                local_path=local_path,
                generated_at=datetime.utcnow(),
                metadata=metadata or {},
            )
        )


class TenderPipelineResult(BaseModel):
    success: bool = True
    tender: Optional[NormalizedTender] = None
    message: Optional[str] = None
    errors: List[str] = Field(default_factory=list)


class TenderBatchPipelineResult(BaseModel):
    success: bool = True
    total: int = 0
    eligible_count: int = 0
    ineligible_count: int = 0
    manual_review_count: int = 0
    failed_count: int = 0
    results: List[TenderPipelineResult] = Field(default_factory=list)


def build_tender_id(
    source: str,
    reference_number: Optional[str],
    title: str,
    issuing_entity: str,
) -> str:
    """
    Create a stable tender ID from key business identifiers.
    Keep it deterministic so the same tender does not duplicate easily.
    """
    import hashlib

    raw = "|".join(
        [
            (source or "").strip().lower(),
            (reference_number or "").strip().lower(),
            (title or "").strip().lower(),
            (issuing_entity or "").strip().lower(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def normalize_submission_method(value: Optional[str]) -> SubmissionMethod:
    if not value:
        return SubmissionMethod.UNKNOWN

    text = value.strip().lower()

    if "email" in text or "e-mail" in text:
        return SubmissionMethod.EMAIL
    if "portal" in text or "etender" in text or "e-tender" in text or "online" in text:
        return SubmissionMethod.PORTAL
    if "courier" in text:
        return SubmissionMethod.COURIER
    if "physical" in text or "hand deliver" in text or "hand-deliver" in text or "deposit" in text:
        return SubmissionMethod.PHYSICAL

    return SubmissionMethod.UNKNOWN


def normalize_briefing_requirement(value: Optional[str]) -> BriefingRequirement:
    if not value:
        return BriefingRequirement.UNKNOWN

    text = value.strip().lower()

    if "compulsory" in text or "mandatory" in text:
        return BriefingRequirement.COMPULSORY
    if "optional" in text or "non-compulsory" in text or "not compulsory" in text:
        return BriefingRequirement.OPTIONAL
    if "none" in text or "no briefing" in text or "no site inspection" in text:
        return BriefingRequirement.NONE

    return BriefingRequirement.UNKNOWN


def normalize_document_type(value: Optional[str]) -> DocumentType:
    if not value:
        return DocumentType.OTHER

    text = value.strip().lower()

    if "boq" in text or "bill of quantities" in text:
        return DocumentType.BOQ
    if "scope" in text or "specification" in text:
        return DocumentType.SCOPE
    if "drawing" in text or "plan" in text:
        return DocumentType.DRAWING
    if "sbd" in text:
        return DocumentType.SBD
    if "pricing" in text:
        return DocumentType.PRICING_SCHEDULE
    if "terms" in text or "conditions" in text:
        return DocumentType.TERMS
    if "notice" in text or "advert" in text or "invitation" in text:
        return DocumentType.TENDER_NOTICE

    return DocumentType.OTHER


def make_normalized_tender(
    *,
    source: str,
    title: str,
    issuing_entity: str,
    reference_number: Optional[str] = None,
    source_type: Optional[str] = None,
    source_url: Optional[str] = None,
    notice_url: Optional[str] = None,
    harvested_at: Optional[datetime] = None,
    published_at: Optional[datetime] = None,
    closing_at: Optional[datetime] = None,
    compulsory_briefing_at: Optional[datetime] = None,
    optional_briefing_at: Optional[datetime] = None,
    submission_method: SubmissionMethod = SubmissionMethod.UNKNOWN,
    portal_name: Optional[str] = None,
    portal_url: Optional[str] = None,
    submission_email: Optional[str] = None,
    submission_address: Optional[str] = None,
    briefing_requirement: BriefingRequirement = BriefingRequirement.UNKNOWN,
    briefing_location: Optional[str] = None,
    description: Optional[str] = None,
    scope_summary: Optional[str] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    region: Optional[str] = None,
    province: Optional[str] = None,
    municipality: Optional[str] = None,
    estimated_value: Optional[float] = None,
    currency: str = "ZAR",
    cidb_grading: Optional[str] = None,
    contact_details: Optional[List[ContactDetails]] = None,
    documents: Optional[List[TenderDocument]] = None,
    raw_text: Optional[str] = None,
    raw_data: Optional[Dict[str, Any]] = None,
) -> NormalizedTender:
    tender_id = build_tender_id(
        source=source,
        reference_number=reference_number,
        title=title,
        issuing_entity=issuing_entity,
    )

    return NormalizedTender(
        tender_id=tender_id,
        reference_number=reference_number,
        title=title,
        issuing_entity=issuing_entity,
        source=source,
        source_type=source_type,
        source_url=source_url,
        notice_url=notice_url,
        harvested_at=harvested_at or datetime.utcnow(),
        published_at=published_at,
        closing_at=closing_at,
        compulsory_briefing_at=compulsory_briefing_at,
        optional_briefing_at=optional_briefing_at,
        submission_method=submission_method,
        portal_name=portal_name,
        portal_url=portal_url,
        submission_email=submission_email,
        submission_address=submission_address,
        briefing_requirement=briefing_requirement,
        briefing_location=briefing_location,
        description=description,
        scope_summary=scope_summary,
        category=category,
        subcategory=subcategory,
        region=region,
        province=province,
        municipality=municipality,
        estimated_value=estimated_value,
        currency=currency,
        cidb_grading=cidb_grading,
        contact_details=contact_details or [],
        documents=documents or [],
        raw_text=raw_text,
        raw_data=raw_data or {},
        status=TenderStatus.NORMALIZED,
    )
