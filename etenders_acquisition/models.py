from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class CanonicalRecord:
    source_id: str
    record_uid: str
    entity_type: str

    title: str
    normalized_title: str
    url: str

    closing_date: Optional[datetime] = None

    fingerprint: str = ""

    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)

    raw: Dict[str, Any] = field(default_factory=dict)
