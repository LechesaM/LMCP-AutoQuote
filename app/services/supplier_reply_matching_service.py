from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional

from app.services.supplier_request_registry_service import SupplierRequestRegistryService

logger = logging.getLogger(__name__)


class SupplierReplyMatchingService:
    @classmethod
    def match_reply_metadata(
        cls,
        *,
        from_email: str,
        from_name: str = "",
        subject: str = "",
        body_text: str = "",
        received_at: Optional[str] = None,
        attachment_names: Optional[List[str]] = None,
        buyer_rfq_number: str = "",
        lmcp_quote_number: str = "",
    ) -> Dict[str, Any]:
        return SupplierRequestRegistryService.find_candidate_requests_for_reply(
            from_email=from_email,
            from_name=from_name,
            subject=subject,
            body_text=body_text,
            received_at=received_at,
            attachment_names=attachment_names,
            buyer_rfq_number=buyer_rfq_number,
            lmcp_quote_number=lmcp_quote_number,
        )

    @classmethod
    def attach_match_to_result(
        cls,
        result: Dict[str, Any],
        reply_match: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = deepcopy(result)
        payload["supplier_reply_match"] = reply_match
        payload["supplier_reply_best_match"] = reply_match.get("best_match")
        return payload
