import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

import httpx


def _normalize_base_url(raw: str) -> str:
    """
    Accept either:
      - https://ocds-api.etenders.gov.za
      - https://ocds-api.etenders.gov.za/
      - https://ocds-api.etenders.gov.za/api   (we will remove trailing /api)
    and return the clean base URL without trailing slash and without /api suffix.
    """
    url = (raw or "").strip().rstrip("/")
    if url.endswith("/api"):
        url = url[:-4]
    return url


OCDS_BASE_URL = _normalize_base_url(
    os.getenv("OCDS_BASE_URL", "https://ocds-api.etenders.gov.za")
)
OCDS_URL = f"{OCDS_BASE_URL}/api/OCDSReleases"

OCDS_PAGE_SIZE = int(os.getenv("OCDS_PAGE_SIZE", "50"))
OCDS_MAX_PAGES = int(os.getenv("OCDS_MAX_PAGES", "5"))
POLL_LOOKBACK_DAYS = int(os.getenv("POLL_LOOKBACK_DAYS", "30"))

# Retry controls (safe defaults)
OCDS_MAX_RETRIES = int(os.getenv("OCDS_MAX_RETRIES", "3"))
OCDS_RETRY_SLEEP_SECONDS = float(os.getenv("OCDS_RETRY_SLEEP_SECONDS", "2"))


def _date_window_iso() -> Tuple[str, str]:
    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(days=POLL_LOOKBACK_DAYS)).date().isoformat()
    date_to = now.date().isoformat()
    return date_from, date_to


def _extract_items(data: Any) -> List[Dict[str, Any]]:
    """
    eTenders OCDS may return:
      - a list directly
      - or a dict containing releases/data
    """
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        items = (
            data.get("releases")
            or data.get("Releases")
            or data.get("data")
            or data.get("Data")
            or []
        )
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict)]
    return []


def _get_with_retries(client: httpx.Client, url: str, params: Dict[str, Any]) -> httpx.Response:
    """
    Retry transient failures. If the server keeps failing (500s), we return the last response
    and let the caller decide whether to stop paging.
    """
    last_exc: Exception | None = None
    last_resp: httpx.Response | None = None

    for attempt in range(1, OCDS_MAX_RETRIES + 1):
        try:
            resp = client.get(url, params=params)
            last_resp = resp

            # Retry on server errors (5xx)
            if resp.status_code >= 500:
                time.sleep(OCDS_RETRY_SLEEP_SECONDS * attempt)
                continue

            return resp

        except Exception as e:
            last_exc = e
            time.sleep(OCDS_RETRY_SLEEP_SECONDS * attempt)

    # If we never got a good response:
    if last_resp is not None:
        return last_resp
    raise RuntimeError(f"OCDS request failed after retries: {last_exc}") from last_exc


def fetch_ocds_releases() -> List[Dict[str, Any]]:
    """
    Fetch releases from eTenders OCDS API.
    Returns a list (possibly empty) of release items.
    Never raises on intermittent API 500s — it will stop paging gracefully.
    """
    releases: List[Dict[str, Any]] = []
    date_from, date_to = _date_window_iso()

    timeout = httpx.Timeout(30.0, connect=10.0)

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for page_number in range(1, OCDS_MAX_PAGES + 1):
            params = {
                "PageNumber": page_number,
                "PageSize": OCDS_PAGE_SIZE,
                "dateFrom": date_from,
                "dateTo": date_to,
            }

            try:
                r = _get_with_retries(client, OCDS_URL, params=params)

                # If server still returns 5xx after retries, stop paging but don't crash worker
                if r.status_code >= 500:
                    print(f"OCDS server error {r.status_code} on page {page_number}; stopping paging.")
                    break

                # Non-200 (like 400/401/403/404) — stop paging; treat as configuration/API change
                if r.status_code != 200:
                    print(f"OCDS unexpected status {r.status_code} on page {page_number}; stopping paging.")
                    break

                data = r.json()
                page_items = _extract_items(data)

                if not page_items:
                    break

                releases.extend(page_items)

            except Exception as e:
                print(f"OCDS request failed on page {page_number}: {e}")
                break

    return releases
