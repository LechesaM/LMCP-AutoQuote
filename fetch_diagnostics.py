import json
import socket
import ssl
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import requests


FETCH_TIMEOUT = 15
FAILURE_DIR = Path("runtime/fetch-failures")
FAILURE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class FetchDiagnostic:
    url: str
    host: str
    success: bool = False

    resolved_ip: Optional[str] = None

    dns_ms: Optional[int] = None
    total_ms: Optional[int] = None

    status: Optional[int] = None
    content_type: Optional[str] = None
    body_bytes: Optional[int] = None

    failure_class: Optional[str] = None
    error: Optional[str] = None


class FetchHealth:
    def __init__(self):
        self.total = 0
        self.success = 0

        self.dns_failures = 0
        self.tls_failures = 0
        self.timeout_failures = 0

        self.http403 = 0
        self.http404 = 0
        self.http5xx = 0

        self.anti_bot = 0
        self.empty_body = 0
        self.unknown = 0

    def record(self, result: FetchDiagnostic):
        self.total += 1

        if result.success:
            self.success += 1
            return

        mapping = {
            "dns": "dns_failures",
            "tls": "tls_failures",
            "timeout": "timeout_failures",
            "http_403": "http403",
            "http_404": "http404",
            "http_5xx": "http5xx",
            "anti_bot": "anti_bot",
            "empty_body": "empty_body",
        }

        field = mapping.get(result.failure_class)

        if field:
            setattr(self, field, getattr(self, field) + 1)
        else:
            self.unknown += 1

    def snapshot(self):
        return self.__dict__


fetch_health = FetchHealth()


def resolve_dns(host: str):
    start = time.time()

    try:
        ip = socket.gethostbyname(host)

        return {
            "ok": True,
            "ip": ip,
            "elapsed_ms": int((time.time() - start) * 1000),
        }

    except Exception as ex:
        return {
            "ok": False,
            "error": str(ex),
            "elapsed_ms": int((time.time() - start) * 1000),
        }


def save_failure(result: FetchDiagnostic):
    filename = FAILURE_DIR / f"{int(time.time() * 1000)}.json"

    with open(filename, "w") as f:
        json.dump(asdict(result), f, indent=2)


def fetch_with_diagnostics(url: str) -> FetchDiagnostic:

    try:
        host = requests.utils.urlparse(url).hostname

        if not host:
            return FetchDiagnostic(
                url=url,
                host="unknown",
                failure_class="url_pattern",
                error="Invalid URL",
            )

    except Exception as ex:
        return FetchDiagnostic(
            url=url,
            host="unknown",
            failure_class="url_pattern",
            error=str(ex),
        )

    diagnostic = FetchDiagnostic(
        url=url,
        host=host,
    )

    dns_result = resolve_dns(host)

    if not dns_result["ok"]:
        diagnostic.failure_class = "dns"
        diagnostic.error = dns_result["error"]
        diagnostic.dns_ms = dns_result["elapsed_ms"]

        save_failure(diagnostic)
        return diagnostic

    diagnostic.resolved_ip = dns_result["ip"]
    diagnostic.dns_ms = dns_result["elapsed_ms"]

    try:
        started = time.time()

        response = requests.get(
            url,
            timeout=FETCH_TIMEOUT,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "LMCP AutoQuote Diagnostic Probe"
                )
            },
        )

        body = response.text

        diagnostic.total_ms = int(
            (time.time() - started) * 1000
        )

        diagnostic.status = response.status_code
        diagnostic.content_type = response.headers.get(
            "Content-Type"
        )

        diagnostic.body_bytes = len(body.encode())

        if response.status_code == 403:
            diagnostic.failure_class = "http_403"

        elif response.status_code == 404:
            diagnostic.failure_class = "http_404"

        elif response.status_code >= 500:
            diagnostic.failure_class = "http_5xx"

        elif not body.strip():
            diagnostic.failure_class = "empty_body"

        elif any(
            token.lower() in body.lower()
            for token in [
                "captcha",
                "access denied",
                "cloudflare",
            ]
        ):
            diagnostic.failure_class = "anti_bot"

        else:
            diagnostic.success = True

        if not diagnostic.success:
            save_failure(diagnostic)

        return diagnostic

    except requests.exceptions.Timeout as ex:

        diagnostic.failure_class = "timeout"
        diagnostic.error = str(ex)

    except ssl.SSLError as ex:

        diagnostic.failure_class = "tls"
        diagnostic.error = str(ex)

    except Exception as ex:

        msg = str(ex)

        if (
            "certificate" in msg.lower()
            or "ssl" in msg.lower()
        ):
            diagnostic.failure_class = "tls"
        else:
            diagnostic.failure_class = "unknown"

        diagnostic.error = msg

    save_failure(diagnostic)
    return diagnostic
