#!/usr/bin/env python3
import json
import socket
import ssl
import time
import random
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, List

import requests


# =========================
# PATHS
# =========================

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")
FETCH_RUNTIME_DIR = RUNTIME_DIR / "portal_fetch"
SNAPSHOT_DIR = FETCH_RUNTIME_DIR / "snapshots"
LOG_DIR = FETCH_RUNTIME_DIR / "logs"

SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

FETCH_REPORT_FILE = LOG_DIR / "resilient_portal_fetch_report.json"


# =========================
# CONFIG
# =========================

PORTALS = [
    "https://www.etenders.gov.za/Home/opportunities",
    "https://www.etenders.gov.za",
    "https://data.etenders.gov.za",
    "https://www.eskom.co.za/tenderbulletin/",
    "https://transnetetenders.azurewebsites.net/",
    "https://www.nra.co.za/service-provider-zone/tenders/",
]

TIMEOUT_SECONDS = 30
MAX_ATTEMPTS = 4
BACKOFF_BASE_SECONDS = 2

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Mozilla/5.0 LMCP-AutoQuote/1.0 TenderFetch",
]


# =========================
# MODELS
# =========================

@dataclass
class DNSResult:
    host: str
    resolved: bool
    addresses: list
    error: Optional[str]
    duration_ms: int


@dataclass
class TLSResult:
    host: str
    port: int
    success: bool
    tls_version: Optional[str]
    cipher: Optional[str]
    error: Optional[str]
    duration_ms: int


@dataclass
class FetchAttempt:
    attempt: int
    url: str
    success: bool
    status_code: Optional[int]
    content_type: Optional[str]
    body_bytes: int
    failure_class: Optional[str]
    error: Optional[str]
    duration_ms: int


@dataclass
class PortalFetchResult:
    url: str
    host: str
    checked_at: str
    dns: dict
    tls: dict
    attempts: list
    final_success: bool
    final_status_code: Optional[int]
    final_failure_class: Optional[str]
    snapshot_path: Optional[str]
    snapshot_sha256: Optional[str]

@dataclass
class DNSResult:
    host: str
    resolved: bool
    addresses: list
    error: Optional[str]
    duration_ms: int


@dataclass
class TLSResult:
    host: str
    port: int
    success: bool
    tls_version: Optional[str]
    cipher: Optional[str]
    error: Optional[str]
    duration_ms: int


@dataclass
class FetchAttempt:
    attempt: int
    url: str
    success: bool
    status_code: Optional[int]
    content_type: Optional[str]
    body_bytes: int
    failure_class: Optional[str]
    error: Optional[str]
    duration_ms: int


@dataclass
class PortalFetchResult:
    url: str
    host: str
    checked_at: str
    dns: dict
    tls: dict
    attempts: list
    final_success: bool
    final_status_code: Optional[int]
    final_failure_class: Optional[str]
    snapshot_path: Optional[str]
    snapshot_sha256: Optional[str]

# =========================
# HELPERS
# =========================

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def ms_since(start):
    return int((time.time() - start) * 1000)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def safe_host_slug(host):
    return host.replace(".", "_").replace(":", "_")


def classify_error(status_code=None, error=None, body=None):
    err = str(error or "").lower()
    body_text = ""

    if body:
        try:
            body_text = body[:3000].decode("utf-8", errors="ignore").lower()
        except Exception:
            body_text = ""

    if "name or service not known" in err or "failed to resolve" in err or "nameresolutionerror" in err:
        return "dns"

    if "connection refused" in err or "max retries exceeded" in err:
        return "connect"

    if "ssl" in err or "certificate" in err:
        return "tls"

    if "timed out" in err or "timeout" in err:
        return "timeout"

    if status_code == 403:
        return "http_403"

    if status_code == 404:
        return "http_404"

    if status_code and 500 <= status_code <= 599:
        return "http_5xx"

    if status_code and 300 <= status_code <= 399:
        return "redirect"

    anti_bot_terms = [
        "cloudflare",
        "access denied",
        "captcha",
        "bot detection",
        "checking your browser",
    ]

    if any(term in body_text for term in anti_bot_terms):
        return "anti_bot"

    if status_code == 200 and body is not None and len(body) == 0:
        return "empty_body"

    if status_code and status_code >= 400:
        return "http_error"

    if error:
        return "unknown"

    return None


# =========================
# DNS / TLS
# =========================

def check_dns(host):
    start = time.time()

    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addresses = sorted({info[4][0] for info in infos})

        return DNSResult(
            host=host,
            resolved=True,
            addresses=addresses,
            error=None,
            duration_ms=ms_since(start),
        )

    except Exception as e:
        return DNSResult(
            host=host,
            resolved=False,
            addresses=[],
            error=str(e),
            duration_ms=ms_since(start),
        )


def check_tls(host, port=443):
    start = time.time()

    try:
        context = ssl.create_default_context()

        with socket.create_connection((host, port), timeout=TIMEOUT_SECONDS) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cipher = ssock.cipher()

                return TLSResult(
                    host=host,
                    port=port,
                    success=True,
                    tls_version=ssock.version(),
                    cipher=cipher[0] if cipher else None,
                    error=None,
                    duration_ms=ms_since(start),
                )

    except Exception as e:
        return TLSResult(
            host=host,
            port=port,
            success=False,
            tls_version=None,
            cipher=None,
            error=str(e),
            duration_ms=ms_since(start),
        )


# =========================
# FETCH
# =========================

def build_session():
    session = requests.Session()

    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-ZA,en;q=0.9",
        "Connection": "keep-alive",
    })

    return session


def fetch_once(session, url, attempt):
    start = time.time()

    try:
        response = session.get(
            url,
            timeout=TIMEOUT_SECONDS,
            allow_redirects=True,
        )

        body = response.content or b""
        failure_class = classify_error(
            status_code=response.status_code,
            body=body,
        )

        success = response.status_code == 200 and failure_class is None

        return FetchAttempt(
            attempt=attempt,
            url=url,
            success=success,
            status_code=response.status_code,
            content_type=response.headers.get("content-type"),
            body_bytes=len(body),
            failure_class=failure_class,
            error=None,
            duration_ms=ms_since(start),
        ), response

    except Exception as e:
        return FetchAttempt(
            attempt=attempt,
            url=url,
            success=False,
            status_code=None,
            content_type=None,
            body_bytes=0,
            failure_class=classify_error(error=e),
            error=str(e),
            duration_ms=ms_since(start),
        ), None


def save_snapshot(url, response):
    if response is None:
        return None, None

    body = response.content or b""

    if not body:
        return None, None

    parsed = urlparse(url)
    host_slug = safe_host_slug(parsed.netloc)
    digest = sha256_bytes(body)

    suffix = ".html"

    content_type = response.headers.get("content-type", "").lower()

    if "json" in content_type:
        suffix = ".json"
    elif "pdf" in content_type:
        suffix = ".pdf"
    elif "zip" in content_type:
        suffix = ".zip"

    filename = f"{host_slug}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{digest[:10]}{suffix}"
    path = SNAPSHOT_DIR / filename

    with path.open("wb") as f:
        f.write(body)

    return str(path), digest


def resilient_fetch(url):
    parsed = urlparse(url)
    host = parsed.netloc

    dns_result = check_dns(host)
    tls_result = check_tls(host) if dns_result.resolved else TLSResult(
        host=host,
        port=443,
        success=False,
        tls_version=None,
        cipher=None,
        error="skipped_due_to_dns_failure",
        duration_ms=0,
    )

    attempts = []
    final_response = None

    session = build_session()

    for attempt_no in range(1, MAX_ATTEMPTS + 1):
        attempt, response = fetch_once(session, url, attempt_no)
        attempts.append(asdict(attempt))

        if attempt.success:
            final_response = response
            break

        sleep_for = BACKOFF_BASE_SECONDS * attempt_no + random.uniform(0.2, 1.2)
        time.sleep(sleep_for)

    successful_attempts = [a for a in attempts if a["success"]]
    last_attempt = attempts[-1] if attempts else {}

    snapshot_path = None
    snapshot_sha256 = None

    if successful_attempts and final_response is not None:
        snapshot_path, snapshot_sha256 = save_snapshot(url, final_response)

    return PortalFetchResult(
        url=url,
        host=host,
        checked_at=now_iso(),
        dns=asdict(dns_result),
        tls=asdict(tls_result),
        attempts=attempts,
        final_success=bool(successful_attempts),
        final_status_code=last_attempt.get("status_code"),
        final_failure_class=None if successful_attempts else last_attempt.get("failure_class"),
        snapshot_path=snapshot_path,
        snapshot_sha256=snapshot_sha256,
    )


# =========================
# MAIN
# =========================

def main():
    results = []

    for url in PORTALS:
        print(f"Fetching: {url}")
        result = resilient_fetch(url)
        results.append(asdict(result))

        print(
            f"  success={result.final_success} "
            f"dns={result.dns.get('resolved')} "
            f"status={result.final_status_code} "
            f"failure={result.final_failure_class}"
        )

    summary = {
        "generated_at": now_iso(),
        "portal_count": len(PORTALS),
        "success_count": sum(1 for r in results if r["final_success"]),
        "failure_count": sum(1 for r in results if not r["final_success"]),
        "results": results,
    }

    write_json(FETCH_REPORT_FILE, summary)

    print("\nResilient portal fetch complete")
    print(f"Success: {summary['success_count']}")
    print(f"Failed: {summary['failure_count']}")
    print(f"Report: {FETCH_REPORT_FILE}")


if __name__ == "__main__":
    main()
