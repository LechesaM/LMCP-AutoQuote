import hashlib
import re
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests


RFQ_KEYWORDS = [
    "rfq",
    "request for quotation",
    "quotation",
    "quote",
    "tender",
    "tenders",
    "bid",
    "bids",
    "procurement",
    "supply chain",
    "supply-chain",
    "scm",
]

DOCUMENT_EXTENSIONS = [
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
]

HEADERS = {
    "User-Agent": "LMCP-AutoQuote/1.0 (+https://localhost)",
    "Accept-Language": "en-ZA,en;q=0.9",
}


class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: List[Dict[str, str]] = []
        self._current_href: Optional[str] = None
        self._current_text_parts: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            attrs_dict = dict(attrs)
            self._current_href = attrs_dict.get("href")
            self._current_text_parts = []

    def handle_data(self, data):
        if self._current_href is not None:
            self._current_text_parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._current_href is not None:
            text = unescape(" ".join(self._current_text_parts)).strip()
            self.links.append(
                {
                    "href": self._current_href.strip(),
                    "text": re.sub(r"\s+", " ", text),
                }
            )
            self._current_href = None
            self._current_text_parts = []


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def same_domain(url_a: str, url_b: str) -> bool:
    try:
        host_a = urlparse(url_a).netloc.replace("www.", "")
        host_b = urlparse(url_b).netloc.replace("www.", "")
        return host_a == host_b
    except Exception:
        return False


def fetch_html(url: str) -> str:
    response = requests.get(url, timeout=45, headers=HEADERS, allow_redirects=True)
    response.raise_for_status()
    if "text/html" not in response.headers.get("content-type", "").lower():
        return ""
    return response.text


def extract_links(base_url: str, html: str) -> List[Dict[str, str]]:
    parser = AnchorParser()
    parser.feed(html)

    results: List[Dict[str, str]] = []

    for item in parser.links:
        href = item.get("href") or ""
        text = item.get("text") or ""

        if not href or href.startswith("#"):
            continue

        absolute_url = urljoin(base_url, href)
        results.append({"text": text, "url": absolute_url})

    return results


def looks_like_procurement_link(text: str, url: str) -> bool:
    text_n = normalize(text)
    url_n = normalize(url)

    if any(ext in url_n for ext in DOCUMENT_EXTENSIONS):
        return True

    return any(keyword in text_n or keyword in url_n for keyword in RFQ_KEYWORDS)


def make_candidate_pages(homepage_url: str, homepage_links: List[Dict[str, str]]) -> List[str]:
    candidates = set()
    candidates.add(homepage_url.rstrip("/"))

    common_paths = [
        "/tenders",
        "/tender",
        "/rfq",
        "/rfqs",
        "/quotation",
        "/quotations",
        "/procurement",
        "/bids",
        "/bid",
        "/supply-chain-management",
        "/scm",
    ]

    for path in common_paths:
        candidates.add(homepage_url.rstrip("/") + path)

    for link in homepage_links:
        link_url = link["url"]
        link_text = link["text"]

        if looks_like_procurement_link(link_text, link_url) and same_domain(homepage_url, link_url):
            candidates.add(link_url)

    return list(candidates)


def make_external_id(source_key: str) -> str:
    return hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:40]


def parse_closing_date(text: str) -> Optional[datetime]:
    if not text:
        return None

    patterns = [
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue

        value = match.group(1)

        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                pass

    return None


def extract_opportunities_from_page(page_url: str, page_html: str) -> List[Dict[str, Optional[str]]]:
    page_links = extract_links(page_url, page_html)
    results: List[Dict[str, Optional[str]]] = []
    seen = set()

    for link in page_links:
        title = (link["text"] or "").strip()
        url = link["url"]

        if not title and not url:
            continue

        if not looks_like_procurement_link(title, url):
            continue

        key = f"{title}|{url}"
        if key in seen:
            continue
        seen.add(key)

        combined_text = f"{title} {url}"
        closing_date = parse_closing_date(combined_text)

        is_document = any(url.lower().endswith(ext) for ext in DOCUMENT_EXTENSIONS)

        results.append(
            {
                "title": title[:500] if title else "RFQ / Tender Notice",
                "description": title[:1000] if title else "Department website RFQ / tender notice",
                "source_url": page_url,
                "document_url": url if is_document else None,
                "detail_url": None if is_document else url,
                "closing_date": closing_date,
            }
        )

    return results


def harvest_department_rfqs() -> Dict[str, int]:
    from app.database import SessionLocal
    from app.models import DepartmentSource, Opportunity
    from app.scoring import is_supply_delivery_opportunity, score_opportunity
    from app.intelligence import analyze_opportunity

    db = SessionLocal()

    try:
        departments = (
            db.query(DepartmentSource)
            .filter(DepartmentSource.is_active == True)
            .order_by(DepartmentSource.name.asc())
            .all()
        )

        departments_checked = 0
        pages_checked = 0
        opportunities_added = 0
        opportunities_existing = 0
        skipped_not_supply = 0
        errors = 0

        for department in departments:
            departments_checked += 1
            department.last_checked_at = datetime.utcnow()

            try:
                homepage_html = fetch_html(department.homepage_url)
                homepage_links = extract_links(department.homepage_url, homepage_html) if homepage_html else []

                if not department.rfq_url:
                    for link in homepage_links:
                        if looks_like_procurement_link(link["text"], link["url"]) and same_domain(department.homepage_url, link["url"]):
                            department.rfq_url = link["url"]
                            break

                candidate_pages = make_candidate_pages(department.homepage_url, homepage_links)

                if department.rfq_url:
                    candidate_pages.insert(0, department.rfq_url)

                dedup_pages = []
                seen_pages = set()
                for page in candidate_pages:
                    page_key = page.strip()
                    if page_key and page_key not in seen_pages:
                        seen_pages.add(page_key)
                        dedup_pages.append(page_key)

                for page_url in dedup_pages[:12]:
                    try:
                        page_html = fetch_html(page_url)
                        if not page_html:
                            continue

                        pages_checked += 1
                        extracted = extract_opportunities_from_page(page_url, page_html)

                        for item in extracted:
                            title = item["title"] or "RFQ / Tender Notice"
                            description = item["description"] or ""
                            detail_url = item["detail_url"]
                            document_url = item["document_url"]
                            closing_date = item["closing_date"]

                            is_supply = is_supply_delivery_opportunity(title, description)
                            if not is_supply:
                                skipped_not_supply += 1
                                continue

                            unique_source = document_url or detail_url or page_url
                            external_id = make_external_id(
                                f"department_site|{department.name}|{title}|{unique_source}"
                            )

                            existing = (
                                db.query(Opportunity)
                                .filter(Opportunity.external_id == external_id)
                                .first()
                            )

                            if existing:
                                opportunities_existing += 1
                                continue

                            score = score_opportunity(title, description)
                            analysis = analyze_opportunity(
                                title=title,
                                description=description,
                                score=score,
                                is_supply_delivery=is_supply,
                            )

                            row = Opportunity(
                                source="department_site",
                                external_id=external_id,
                                title=title[:500],
                                description=description,
                                published_at=datetime.utcnow(),
                                closing_date=closing_date,
                                status="new",
                                score=score,
                                source_url=detail_url or page_url,
                                document_url=document_url,
                                category=analysis["category"],
                                preferred_sector=analysis["preferred_sector"],
                                review_status=analysis["review_status"],
                                decision_reason=analysis["decision_reason"],
                            )

                            db.add(row)
                            opportunities_added += 1

                    except Exception:
                        errors += 1
                        continue

                department.last_success_at = datetime.utcnow()

            except Exception:
                errors += 1
                continue

        db.commit()

        return {
            "departments_checked": departments_checked,
            "pages_checked": pages_checked,
            "opportunities_added": opportunities_added,
            "opportunities_existing": opportunities_existing,
            "skipped_not_supply": skipped_not_supply,
            "errors": errors,
        }

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
