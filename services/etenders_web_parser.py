from __future__ import annotations

import logging
import re
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
import urllib3
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.exceptions import InsecureRequestWarning, NotOpenSSLWarning
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=NotOpenSSLWarning)
urllib3.disable_warnings(InsecureRequestWarning)

DEFAULT_TIMEOUT = 45
ETENDERS_SITE_BASE = "https://www.etenders.gov.za/"
ETENDERS_ACTIVE_OPPS_URL = "https://www.etenders.gov.za/Home/opportunities?id=1"


@dataclass
class ETendersParserConfig:
    timeout: int = DEFAULT_TIMEOUT
    verify_ssl: bool = False
    html_pages_to_try: int = 3
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    )


class ETendersWebParser:
    """
    eTenders scraper V2 (NO API).

    Strategy:
    1. Fetch the public eTenders opportunities page
    2. Parse only likely tender blocks/rows/cards
    3. Aggressively reject page-shell, filter, login, and navigation junk
    4. Return normalized opportunities
    """

    def __init__(self, config: Optional[ETendersParserConfig] = None) -> None:
        self.config = config or ETendersParserConfig()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.config.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-ZA,en;q=0.9",
                "Connection": "keep-alive",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            }
        )
        self._configure_session_retries()

    def _configure_session_retries(self) -> None:
        retry = Retry(
            total=2,
            connect=2,
            read=2,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def harvest(self) -> List[Dict[str, Any]]:
        try:
            items = self._harvest_from_html()
            if items:
                logger.info("[eTenders] HTML scrape succeeded | count=%s", len(items))
                return self._dedupe(items)
        except Exception as exc:
            logger.exception("[eTenders] HTML scrape failed: %s", exc)

        return []

    def _harvest_from_html(self) -> List[Dict[str, Any]]:
        urls_to_try = [
            ETENDERS_ACTIVE_OPPS_URL,
            "https://www.etenders.gov.za/Home/opportunities",
            "https://www.etenders.gov.za/",
        ]

        all_items: List[Dict[str, Any]] = []
        seen = set()

        for url in urls_to_try:
            html = self._fetch_html(url)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")

            # Try the most structured nodes first.
            candidates = []
            candidates.extend(soup.find_all("tr"))
            candidates.extend(soup.find_all("article"))
            candidates.extend(soup.find_all("section"))
            candidates.extend(soup.find_all("li"))
            candidates.extend(soup.find_all("div"))

            for block in candidates:
                item = self._parse_candidate_block(block, base_url=url)
                if not item:
                    continue

                key = (
                    item.get("reference_number")
                    or item.get("buyer_rfq_number")
                    or item.get("title")
                    or item.get("external_id")
                )
                if not key or key in seen:
                    continue
                seen.add(key)
                all_items.append(item)

        return all_items

    def _fetch_html(self, url: str) -> str:
        response = self.session.get(
            url,
            timeout=self.config.timeout,
            verify=self.config.verify_ssl,
        )
        response.raise_for_status()
        return response.text or ""

    def _parse_candidate_block(self, block: Any, base_url: str) -> Optional[Dict[str, Any]]:
        text = self._clean_text(block.get_text(" ", strip=True))
        if not text:
            return None

        if len(text) < 80:
            return None

        lowered = text.lower()

        if self._looks_like_ui_junk(text):
            return None

        if not self._looks_tenderish(text):
            return None

        if not self._looks_supply_or_goods(text):
            return None

        if self._looks_blocked_scope(text):
            return None

        if self._looks_compulsory_briefing(text):
            return None

        reference = self._extract_reference_from_text(text)
        if not self._is_good_reference(reference):
            return None

        title = self._extract_title(block, text)
        if not title:
            return None

        if self._looks_like_ui_junk(title):
            return None

        links = self._extract_links(block, base_url=base_url)
        if not links:
            links = [{"title": "Opportunity", "url": ETENDERS_ACTIVE_OPPS_URL}]

        closing_at = self._extract_closing_date_from_text(text)
        buyer_email = self._extract_email(text)
        province = self._extract_province(title, text)
        submission_method = self._infer_submission_method(text, links)

        primary_url = links[0]["url"] if links else ETENDERS_ACTIVE_OPPS_URL

        return {
            "source": "etenders",
            "source_type": "web_scraper_v2",
            "portal_name": "eTenders",
            "portal_base_url": ETENDERS_SITE_BASE,
            "portal_url": ETENDERS_ACTIVE_OPPS_URL,
            "title": title[:250],
            "description": text[:4000],
            "buyer_name": self._extract_buyer_name(text),
            "buyer_rfq_number": reference,
            "rfq_number": reference,
            "reference_number": reference,
            "external_id": reference,
            "external_url": primary_url,
            "ocid": None,
            "release_id": None,
            "status": "active",
            "published_at": None,
            "closing_at": closing_at,
            "submission_method": submission_method,
            "buyer_email": buyer_email,
            "recipient_email": buyer_email,
            "province": province,
            "briefing_required": False,
            "documents": [
                {
                    "id": "",
                    "title": link["title"],
                    "url": link["url"],
                    "document_type": "",
                    "format": "",
                    "date_published": None,
                }
                for link in links
            ],
            "document_urls": [link["url"] for link in links if link.get("url")],
            "eligible": False,
            "quote_ready": False,
            "raw_release": None,
            "harvested_at": datetime.now(timezone.utc).isoformat(),
        }

    def _extract_title(self, block: Any, full_text: str) -> str:
        selectors = ["h1", "h2", "h3", "h4", "strong", "b", "a", "td"]
        for selector in selectors:
            element = block.find(selector)
            if element:
                title = self._clean_text(element.get_text(" ", strip=True))
                if 8 <= len(title) <= 220 and not self._looks_like_ui_junk(title):
                    return title

        parts = re.split(r"\s{2,}|\s\|\s| - ", full_text)
        for part in parts:
            cleaned = self._clean_text(part)
            if 8 <= len(cleaned) <= 220 and not self._looks_like_ui_junk(cleaned):
                return cleaned

        return full_text[:140].rsplit(" ", 1)[0].strip()

    def _extract_links(self, block: Any, base_url: str) -> List[Dict[str, str]]:
        links: List[Dict[str, str]] = []
        seen = set()

        for anchor in block.find_all("a", href=True):
            href = self._clean_text(anchor.get("href"))
            if not href:
                continue

            full_url = urljoin(base_url, href)
            if not full_url.startswith("http"):
                continue

            title = self._clean_text(anchor.get_text(" ", strip=True)) or "Document"

            if self._looks_like_ui_junk(title) and self._looks_like_ui_junk(full_url):
                continue

            key = (title, full_url)
            if key in seen:
                continue
            seen.add(key)

            links.append({"title": title[:200], "url": full_url})

        return links[:10]

    def _extract_buyer_name(self, text: str) -> str:
        patterns = [
            r"(City of [A-Za-z\s]+)",
            r"(Department of [A-Za-z&,\-\s]+)",
            r"(Municipality [A-Za-z\s]+)",
            r"([A-Z][A-Za-z\s]+ Municipality)",
            r"(National Treasury)",
            r"(Eskom)",
            r"(Transnet)",
            r"(SANRAL)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return self._clean_text(match.group(1))

        return ""

    def _looks_like_ui_junk(self, text: str) -> bool:
        lowered = (text or "").lower()

        junk_patterns = [
            "login required",
            "currently advertised",
            "listing all currently advertised tender opportunities",
            "quickfind",
            "advanced search",
            "please note",
            "category - choose one or more",
            "provinces - choose one or more",
            "organ of state - choose one or more",
            "download excel",
            "download pdf",
            "bookmark feature",
            "save tender",
            "notifications",
            "loading, please wait",
            "use advanced search",
            "filters category",
            "search by tender number",
            "search by maaa number",
            "search by supplier name",
            "reset all filters",
            "new feature alert",
            "got it, thanks",
            "official login",
            "supplier login",
            "currently advertised awarded cancelled closed",
        ]
        return any(pattern in lowered for pattern in junk_patterns)

    def _looks_tenderish(self, text: str) -> bool:
        lowered = text.lower()
        markers = [
            "tender",
            "bid",
            "rfq",
            "request for quotation",
            "quotation",
            "quote",
            "advertised",
            "closing",
        ]
        return any(marker in lowered for marker in markers)

    def _looks_supply_or_goods(self, text: str) -> bool:
        lowered = text.lower()
        markers = [
            "supply",
            "delivery",
            "goods",
            "supply and delivery",
            "supply of",
            "delivery of",
            "purchase",
        ]
        return any(marker in lowered for marker in markers)

    def _looks_blocked_scope(self, text: str) -> bool:
        lowered = text.lower()
        blocked = [
            "medical",
            "pharmaceutical",
            "clinic",
            "hospital",
            "diesel",
            "petrol",
            "fuel",
            "construction",
            "civil",
            "building",
            "consulting",
            "maintenance",
            "repair",
            "installation",
            "services:",
            "services ",
            "expression of interest",
            "eoi",
            "award notice",
            "cancelled tender",
            "procurement plan",
            "supplier registration",
            "vendor registration",
            "database registration",
            "tender results",
        ]
        return any(term in lowered for term in blocked)

    def _looks_compulsory_briefing(self, text: str) -> bool:
        lowered = text.lower()

        if "non-compulsory briefing" in lowered or "non compulsory briefing" in lowered:
            return False

        markers = [
            "compulsory briefing",
            "mandatory briefing",
            "compulsory site inspection",
            "mandatory site inspection",
            "compulsory clarification meeting",
            "mandatory clarification meeting",
        ]
        return any(marker in lowered for marker in markers)

    def _extract_reference_from_text(self, text: str) -> str:
        if not text:
            return ""

        patterns = [
            r"\b(?:RFQ|RFP|BID|TENDER|TNDR|QUOTATION|QUOTE|SCM|Q)\s*[:#/\-]?\s*([A-Z0-9][A-Z0-9/_\-.]{3,})\b",
            r"\b([A-Z]{2,10}[/-][A-Z0-9][A-Z0-9/_\-.]{2,})\b",
            r"\b([A-Z]{1,5}\d{4,})\b",
            r"\b(\d{6,})\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                value = self._clean_text(match.group(1)).upper()
                value = re.sub(r"[^A-Z0-9/_\-.]", "", value)
                return value.strip("._-/")

        return ""

    def _is_good_reference(self, reference: str) -> bool:
        reference = self._clean_text(reference).upper()
        if not reference:
            return False
        if len(reference) < 5:
            return False
        if reference.isalpha():
            return False
        if reference in {"DETAILS", "VIEW", "DOWNLOAD", "NOTIFICATIONS"}:
            return False
        return bool(re.search(r"\d", reference))

    def _extract_closing_date_from_text(self, text: str) -> Optional[str]:
        if not text:
            return None

        patterns = [
            r"closing date[:\s]+(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
            r"closing[:\s]+(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
            r"(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})",
            r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue

            raw = match.group(1).strip()

            for fmt in ("%d %B %Y", "%d %b %Y", "%Y/%m/%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(raw, fmt)
                    return dt.replace(tzinfo=timezone.utc).isoformat()
                except ValueError:
                    continue

        return None

    def _extract_email(self, text: str) -> str:
        if not text:
            return ""
        match = re.search(
            r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
            text,
            re.IGNORECASE,
        )
        return match.group(0).strip() if match else ""

    def _extract_province(self, title: str, text: str) -> str:
        haystack = f"{title} {text}".lower()
        provinces = [
            "eastern cape",
            "free state",
            "gauteng",
            "kwazulu-natal",
            "limpopo",
            "mpumalanga",
            "national",
            "north west",
            "northern cape",
            "western cape",
        ]
        for province in provinces:
            if province in haystack:
                return province.title()
        return ""

    def _infer_submission_method(self, text: str, links: List[Dict[str, str]]) -> str:
        haystack = " ".join(
            [text] + [f"{x.get('title', '')} {x.get('url', '')}" for x in links]
        ).lower()

        if "email" in haystack or "e-mail" in haystack:
            return "email"
        if "portal" in haystack or "etenders.gov.za" in haystack or "esubmissions" in haystack:
            return "portal"
        if "tender box" in haystack or "sealed envelope" in haystack or "hand delivery" in haystack:
            return "physical"

        return "portal"

    def _dedupe(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen = set()

        for item in items:
            key = (
                item.get("reference_number")
                or item.get("buyer_rfq_number")
                or item.get("external_id")
                or item.get("title")
            )
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        return deduped

    def _clean_text(self, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()


def harvest_etenders_opportunities() -> List[Dict[str, Any]]:
    parser = ETendersWebParser()
    return parser.harvest()
