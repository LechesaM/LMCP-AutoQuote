from __future__ import annotations

import argparse
import hashlib
import json
import socket
import ssl
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse, urlencode

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests

from app.core.runtime_paths import get_runtime_paths
from app.services.live_rfq_store import get_live_rfqs

from scripts.run_etenders_fetch_diagnostics import (
    ETENDERS_PAGINATED_ENDPOINT,
    ETENDERS_OPPORTUNITIES,
    _build_page_params,
    _clean,
    _load_registry_sources,
    _parse_rows,
    _select_etenders_sources,
)


DEFAULT_OUTPUT_DIR = "runtime/harvest_recovery"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_port_for_scheme(scheme: str) -> int:
    return 443 if _clean(scheme).lower() == "https" else 80


def _extract_host_port(page_url: str) -> Tuple[str, int, str]:
    parsed = urlparse(page_url)
    host = _clean(parsed.hostname)
    scheme = _clean(parsed.scheme).lower()
    port = parsed.port or _default_port_for_scheme(scheme)
    return host, int(port or 0), scheme


def _probe_dns(host: str, port: int, timeout: int) -> Dict[str, Any]:
    if not host:
        return {
            "status": "skipped",
            "resolved": False,
            "addresses": [],
            "error_class": "missing_host",
            "error_message": "missing_host",
            "timeout_seconds": timeout,
        }
    try:
        infos = socket.getaddrinfo(host, port)
        addresses = sorted(
            {
                _clean(info[4][0])
                for info in infos
                if isinstance(info, tuple) and len(info) > 4 and isinstance(info[4], tuple) and info[4]
            }
        )
        return {
            "status": "ok",
            "resolved": True,
            "addresses": addresses,
            "error_class": "",
            "error_message": "",
            "timeout_seconds": timeout,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "resolved": False,
            "addresses": [],
            "error_class": exc.__class__.__name__,
            "error_message": _clean(exc)[:500],
            "timeout_seconds": timeout,
        }


def _probe_tcp(host: str, port: int, timeout: int, *, dns_resolved: bool) -> Dict[str, Any]:
    if not host:
        return {
            "status": "skipped",
            "reachable": False,
            "error_class": "missing_host",
            "error_message": "missing_host",
            "timeout_seconds": timeout,
        }
    if not dns_resolved:
        return {
            "status": "skipped",
            "reachable": False,
            "error_class": "dns_failed",
            "error_message": "dns_failed",
            "timeout_seconds": timeout,
        }
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {
                "status": "ok",
                "reachable": True,
                "error_class": "",
                "error_message": "",
                "timeout_seconds": timeout,
            }
    except socket.timeout as exc:
        return {
            "status": "timeout",
            "reachable": False,
            "error_class": exc.__class__.__name__,
            "error_message": _clean(exc)[:500],
            "timeout_seconds": timeout,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "reachable": False,
            "error_class": exc.__class__.__name__,
            "error_message": _clean(exc)[:500],
            "timeout_seconds": timeout,
        }


def _probe_tls(host: str, port: int, timeout: int, *, scheme: str, tcp_reachable: bool) -> Dict[str, Any]:
    if _clean(scheme).lower() != "https":
        return {
            "status": "skipped",
            "tls_supported": False,
            "protocol": "",
            "cipher": [],
            "error_class": "",
            "error_message": "",
            "timeout_seconds": timeout,
        }
    if not tcp_reachable:
        return {
            "status": "skipped",
            "tls_supported": False,
            "protocol": "",
            "cipher": [],
            "error_class": "tcp_unreachable",
            "error_message": "tcp_unreachable",
            "timeout_seconds": timeout,
        }
    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as raw_socket:
            with context.wrap_socket(raw_socket, server_hostname=host) as tls_socket:
                return {
                    "status": "ok",
                    "tls_supported": True,
                    "protocol": _clean(getattr(tls_socket, "version", lambda: "")()),
                    "cipher": list(getattr(tls_socket, "cipher", lambda: [])() or []),
                    "error_class": "",
                    "error_message": "",
                    "timeout_seconds": timeout,
                }
    except socket.timeout as exc:
        return {
            "status": "timeout",
            "tls_supported": False,
            "protocol": "",
            "cipher": [],
            "error_class": exc.__class__.__name__,
            "error_message": _clean(exc)[:500],
            "timeout_seconds": timeout,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "tls_supported": False,
            "protocol": "",
            "cipher": [],
            "error_class": exc.__class__.__name__,
            "error_message": _clean(exc)[:500],
            "timeout_seconds": timeout,
        }


def _extract_redirect_chain(response: requests.Response) -> List[Dict[str, Any]]:
    chain: List[Dict[str, Any]] = []
    for item in getattr(response, "history", []) or []:
        chain.append(
            {
                "url": _clean(getattr(item, "url", "")),
                "status_code": int(getattr(item, "status_code", 0) or 0),
                "reason": _clean(getattr(item, "reason", "")),
            }
        )
    chain.append(
        {
            "url": _clean(getattr(response, "url", "")),
            "status_code": int(getattr(response, "status_code", 0) or 0),
            "reason": _clean(getattr(response, "reason", "")),
        }
    )
    return chain


def _looks_like_anti_bot(status_code: int, text: str, headers: Dict[str, Any]) -> bool:
    header_blob = " ".join(
        _clean(headers.get(name))
        for name in ("x-robots-tag", "retry-after", "www-authenticate", "server", "location")
    ).lower()
    body_blob = _clean(text[:1500]).lower()
    if status_code in {401, 403, 407, 429}:
        return True
    return any(term in header_blob or term in body_blob for term in ("captcha", "robot", "verify you are human", "access denied", "blocked", "forbidden"))


def _probe_http(page_url: str, timeout: int) -> Dict[str, Any]:
    raw_text = ""
    parsed_json = None
    status_code = 0
    final_url = page_url
    redirect_chain: List[Dict[str, Any]] = []
    content_type = ""
    response_headers: Dict[str, Any] = {}
    exception_class = ""
    exception_message = ""
    response_json_present = False
    response_rows = 0
    try:
        response = requests.get(
            page_url,
            timeout=timeout,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 LMCP-AutoQuote/1.0",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": ETENDERS_OPPORTUNITIES,
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        status_code = int(response.status_code or 0)
        final_url = _clean(response.url)
        redirect_chain = _extract_redirect_chain(response)
        content_type = _clean(response.headers.get("content-type", ""))
        response_headers = {str(key).lower(): _clean(value) for key, value in dict(getattr(response, "headers", {}) or {}).items()}
        raw_text = response.text or ""
        try:
            parsed_json = response.json()
            response_json_present = parsed_json is not None
            response_rows = _parse_rows(parsed_json)
        except Exception:
            parsed_json = None
            response_json_present = False
            response_rows = 0
    except Exception as exc:
        exception_class = exc.__class__.__name__
        exception_message = _clean(exc)[:500]

    response_length = len(raw_text.encode("utf-8")) if raw_text else 0
    response_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest() if raw_text else ""
    http_status = status_code
    http_status_bucket = "ok"
    if exception_class and not http_status:
        http_status_bucket = "exception"
    elif http_status in {401, 403, 407, 429}:
        http_status_bucket = "blocked"
    elif http_status in {404, 410}:
        http_status_bucket = "missing"
    elif http_status in {301, 302, 303, 307, 308}:
        http_status_bucket = "redirect"
    elif exception_class:
        http_status_bucket = "failed"
    elif http_status >= 500:
        http_status_bucket = "server_error"

    return {
        "status": http_status_bucket,
        "http_status": http_status,
        "final_url": final_url,
        "redirect_chain": redirect_chain,
        "response_length": response_length,
        "response_hash": response_hash,
        "response_text_preview": raw_text[:2000],
        "response_json_present": response_json_present,
        "response_rows": response_rows,
        "content_type": content_type,
        "exception_class": exception_class,
        "exception_message": exception_message,
        "response_headers": response_headers,
        "anti_bot_signals": _looks_like_anti_bot(http_status, raw_text, response_headers),
    }


def _classify_root_cause(
    dns_result: Dict[str, Any],
    tcp_result: Dict[str, Any],
    tls_result: Dict[str, Any],
    http_result: Dict[str, Any],
) -> Tuple[str, str]:
    if _clean(dns_result.get("status")).lower() == "failed":
        return "dns", "DNS resolution failed before the page could be fetched."
    tcp_status = _clean(tcp_result.get("status")).lower()
    tcp_error = _clean(tcp_result.get("error_message")).lower()
    if tcp_status == "timeout":
        return "network_connectivity", "TCP connect timed out."
    if tcp_status == "failed" and any(term in tcp_error for term in ("refused", "unreachable", "no route", "network is unreachable", "connection aborted")):
        return "firewall_proxy", "TCP connect failed or was refused."
    if _clean(tls_result.get("status")).lower() == "failed":
        return "tls_ssl", "TLS handshake failed."
    http_status = int(http_result.get("http_status") or 0)
    http_exception = _clean(http_result.get("exception_class")).lower()
    http_message = _clean(http_result.get("exception_message")).lower()
    if "proxy" in http_exception or "proxy" in http_message:
        return "firewall_proxy", "Proxy configuration or proxy-mediated connection failure."
    if http_result.get("anti_bot_signals"):
        return "anti_bot", "HTTP response or headers indicate access restriction or bot protection."
    if http_status in {401, 403, 407, 429}:
        return "anti_bot", "HTTP access was blocked or challenged."
    if http_status in {404, 410}:
        return "incorrect_url_pattern", "HTTP indicates a stale or invalid URL pattern."
    if _clean(http_result.get("status")).lower() == "redirect":
        return "incorrect_url_pattern", "Redirect chain suggests a stale or changed endpoint."
    if http_exception and http_status == 0 and "timeout" in http_exception:
        return "network_connectivity", "HTTP request timed out."
    if http_exception:
        return "unknown", "HTTP request raised an exception without a more specific stage failure."
    if http_status >= 500:
        return "network_connectivity", "Server-side failure or upstream availability problem."
    if http_status > 0:
        return "http", "HTTP response received; no stronger connectivity failure detected."
    return "unknown", "No decisive failure signal captured."


def _diagnose_page_connectivity(
    page_url: str,
    *,
    timeout: int,
    browser_mode: bool = False,
    browser_screenshot_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    started = datetime.now(timezone.utc)
    host, port, scheme = _extract_host_port(page_url)
    dns_result = _probe_dns(host, port, timeout)
    tcp_result = _probe_tcp(host, port, timeout, dns_resolved=bool(dns_result.get("resolved")))
    tls_result = _probe_tls(host, port, timeout, scheme=scheme, tcp_reachable=bool(tcp_result.get("reachable")))
    http_result = _probe_http(page_url, timeout)
    root_cause, root_cause_detail = _classify_root_cause(dns_result, tcp_result, tls_result, http_result)

    raw_status = _clean(http_result.get("status")).lower()
    exception_class = _clean(http_result.get("exception_class"))
    exception_message = _clean(http_result.get("exception_message"))
    http_status = int(http_result.get("http_status") or 0)
    redirect_chain = list(http_result.get("redirect_chain") or [])
    response_length = int(http_result.get("response_length") or 0)
    page_status = "ok"
    if root_cause in {"dns", "network_connectivity", "tls_ssl", "firewall_proxy", "anti_bot", "incorrect_url_pattern"}:
        page_status = "failed"
    elif raw_status in {"redirect"}:
        page_status = "redirect"
    elif raw_status in {"blocked", "missing", "server_error", "failed", "exception"}:
        page_status = "failed"
    elif http_status >= 400:
        page_status = "failed"
    elif exception_class and not http_status:
        page_status = "exception"

    screenshot_path = ""
    fetch_mode = "requests"
    if browser_mode:
        fetch_mode = "browser"
        try:
            from playwright.sync_api import sync_playwright  # type: ignore

            browser_screenshot_dir = browser_screenshot_dir or get_runtime_paths().runtime_root / "harvest_recovery" / "screenshots"
            browser_screenshot_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = str(browser_screenshot_dir / f"connectivity_{hashlib.sha1(page_url.encode('utf-8')).hexdigest()[:12]}.png")
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(page_url, wait_until="domcontentloaded", timeout=max(timeout, 1) * 1000)
                page.screenshot(path=screenshot_path, full_page=True)
                final_url = _clean(page.url)
                page_content = page.content() or ""
                response_length = len(page_content.encode("utf-8"))
                redirect_chain = redirect_chain or [{"url": final_url, "status_code": 200, "reason": "browser"}]
                browser.close()
        except Exception as exc:
            if not exception_class:
                exception_class = exc.__class__.__name__
                exception_message = _clean(exc)[:500]
            if not page_status or page_status == "ok":
                page_status = "exception"

    payload = {
        "page_url": page_url,
        "target_url": page_url,
        "host": host,
        "port": port,
        "scheme": scheme,
        "fetch_mode": fetch_mode,
        "status": page_status,
        "http_status": http_status,
        "final_url": _clean(http_result.get("final_url") or page_url),
        "redirect_chain": redirect_chain,
        "response_length": response_length,
        "response_hash": _clean(http_result.get("response_hash")),
        "response_text_preview": _clean(http_result.get("response_text_preview")),
        "response_json_present": bool(http_result.get("response_json_present")),
        "response_rows": int(http_result.get("response_rows") or 0),
        "content_type": _clean(http_result.get("content_type")),
        "exception_class": exception_class,
        "exception_message": exception_message,
        "screenshot_path": screenshot_path,
        "elapsed_seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 3),
        "raw_fetch_result": http_result,
        "dns_resolution_result": dns_result,
        "connection_result": tcp_result,
        "timeout_result": {
            "status": "timeout" if _clean(tcp_result.get("status")).lower() == "timeout" or "timeout" in _clean(http_result.get("exception_message")).lower() or "timeout" in _clean(exception_message).lower() else "ok",
            "stage": "connection" if _clean(tcp_result.get("status")).lower() == "timeout" else ("http" if "timeout" in _clean(http_result.get("exception_message")).lower() or "timeout" in _clean(exception_message).lower() else ""),
            "error_class": _clean(tcp_result.get("error_class")) if _clean(tcp_result.get("status")).lower() == "timeout" else _clean(http_result.get("exception_class")) if "timeout" in _clean(http_result.get("exception_message")).lower() else "",
            "error_message": _clean(tcp_result.get("error_message")) if _clean(tcp_result.get("status")).lower() == "timeout" else _clean(http_result.get("exception_message")) if "timeout" in _clean(http_result.get("exception_message")).lower() else "",
        },
        "redirect_result": {
            "status": "redirected" if len(redirect_chain) > 1 else "none",
            "hop_count": max(len(redirect_chain) - 1, 0),
            "chain": redirect_chain,
            "final_url": _clean(http_result.get("final_url") or page_url),
        },
        "tls_result": tls_result,
        "http_result": http_result,
        "connectivity": {
            "root_cause": root_cause,
            "root_cause_detail": root_cause_detail,
        },
    }
    return payload


def _page_plan(pages: int, limit: int) -> Tuple[int, int]:
    pages = max(1, int(pages or 1))
    limit = max(1, int(limit or 1))
    page_size = max(1, (limit + pages - 1) // pages)
    return pages, page_size


def _write_summary_md(path: Path, payload: Dict[str, Any]) -> None:
    metrics = payload["metrics"]
    lines: List[str] = [
        "# Sprint 8C eTenders Connectivity Diagnostics",
        "",
        f"Generated at: {payload['generated_at']}",
        "",
        "## Guardrails",
        "",
        f"- Portal submission disabled: `{payload['guardrails']['portal_submission_disabled']}`",
        f"- Human approval required: `{payload['guardrails']['human_approval_required']}`",
        f"- Autonomous submission enabled: `{payload['guardrails']['autonomous_submission_enabled']}`",
        "",
        "No source was disabled by this diagnostic.",
        "",
        "## Connectivity Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for key in [
        "pages_requested",
        "pages_fetched",
        "pages_failed",
        "rows_seen",
        "response_bytes_total",
        "dns_failed_pages",
        "connection_failed_pages",
        "tls_failed_pages",
        "proxy_failed_pages",
        "anti_bot_pages",
        "incorrect_url_pages",
        "redirecting_pages",
        "browser_mode_pages",
        "screenshot_count",
    ]:
        lines.append(f"| {key} | {metrics[key]} |")
    lines.extend(["", "## Root Causes", "", "| Root Cause | Count |", "| --- | ---: |"])
    for root_cause, count in metrics["top_root_causes"]:
        lines.append(f"| {root_cause} | {count} |")
    lines.extend(["", "## Page Results", "", "| Page | Host | HTTP | Root Cause | DNS | TCP | TLS | Redirects | Bytes | Exception | Screenshot |", "| --- | --- | ---: | --- | --- | --- | --- | ---: | ---: | --- | --- |"])
    for row in payload["page_results"][:20]:
        lines.append(
            "| {page_index} | {host} | {http} | {root} | {dns} | {tcp} | {tls} | {redirects} | {bytes} | {exc} | {shot} |".format(
                page_index=row["page_index"],
                host=row["host"],
                http=row["http_status"],
                root=row["connectivity"]["root_cause"],
                dns=row["dns_resolution_result"]["status"],
                tcp=row["connection_result"]["status"],
                tls=row["tls_result"]["status"],
                redirects=len(row["redirect_result"]["chain"]),
                bytes=row["response_length"],
                exc=row["exception_class"] or "",
                shot=row["screenshot_path"] or "",
            )
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_etenders_connectivity_diagnostics(
    *,
    pages: int = 20,
    limit: int = 500,
    timeout: int = 20,
    output_dir: Optional[Path] = None,
    browser_mode: bool = False,
    probe_page_fn: Callable[..., Dict[str, Any]] = _diagnose_page_connectivity,
) -> Dict[str, Any]:
    registry_sources, registry_path, checked_paths = _load_registry_sources()
    etenders_sources = _select_etenders_sources(registry_sources)
    pages_requested, page_size = _page_plan(pages, limit)

    page_results: List[Dict[str, Any]] = []
    pages_fetched = 0
    pages_failed = 0
    rows_seen = 0
    response_bytes_total = 0
    redirecting_pages = 0
    browser_mode_pages = 0
    screenshot_count = 0
    root_cause_counts: Counter[str] = Counter()
    exception_counts: Counter[str] = Counter()

    for page_index in range(pages_requested):
        start = page_index * page_size
        page_url = f"{ETENDERS_PAGINATED_ENDPOINT}?{urlencode(_build_page_params(start, page_size))}"
        page = probe_page_fn(
            page_url,
            timeout=timeout,
            browser_mode=browser_mode,
            browser_screenshot_dir=get_runtime_paths().runtime_root / "harvest_recovery" / "screenshots" if browser_mode else None,
        )
        page["page_index"] = page_index
        page["start"] = start
        page["page_size"] = page_size
        page_results.append(page)
        response_bytes_total += int(page.get("response_length") or 0)
        rows_seen += int(page.get("response_rows") or 0)
        root_cause = _clean((page.get("connectivity") or {}).get("root_cause")) or "unknown"
        root_cause_counts[root_cause] += 1
        exception_class = _clean(page.get("exception_class")) or "none"
        exception_counts[exception_class] += 1
        if _clean(page.get("status")).lower() == "ok":
            pages_fetched += 1
        else:
            pages_failed += 1
        if len(page.get("redirect_result", {}).get("chain") or page.get("redirect_chain") or []) > 1:
            redirecting_pages += 1
        if _clean(page.get("fetch_mode")).lower() == "browser":
            browser_mode_pages += 1
        if page.get("screenshot_path"):
            screenshot_count += 1

    metrics = {
        "pages_requested": pages_requested,
        "pages_fetched": pages_fetched,
        "pages_failed": pages_failed,
        "rows_seen": rows_seen,
        "response_bytes_total": response_bytes_total,
        "dns_failed_pages": root_cause_counts.get("dns", 0),
        "connection_failed_pages": root_cause_counts.get("network_connectivity", 0),
        "tls_failed_pages": root_cause_counts.get("tls_ssl", 0),
        "proxy_failed_pages": root_cause_counts.get("firewall_proxy", 0),
        "anti_bot_pages": root_cause_counts.get("anti_bot", 0),
        "incorrect_url_pages": root_cause_counts.get("incorrect_url_pattern", 0),
        "redirecting_pages": redirecting_pages,
        "browser_mode_pages": browser_mode_pages,
        "screenshot_count": screenshot_count,
        "top_root_causes": sorted(root_cause_counts.items(), key=lambda item: (-item[1], item[0])),
        "top_exception_types": sorted(exception_counts.items(), key=lambda item: (-item[1], item[0])),
        "configured_sources": len(registry_sources),
        "etenders_sources": len(etenders_sources),
    }

    output_root = Path(output_dir) if output_dir else get_runtime_paths().runtime_root / "harvest_recovery"
    output_root.mkdir(parents=True, exist_ok=True)
    diagnostics_path = output_root / "etenders_connectivity_diagnostics.json"
    summary_path = output_root / "etenders_connectivity_diagnostics.md"

    payload = {
        "status": "ok",
        "generated_at": _now_iso(),
        "registry_path": registry_path,
        "registry_paths_checked": checked_paths,
        "guardrails": {
            "portal_submission_disabled": True,
            "human_approval_required": True,
            "autonomous_submission_enabled": False,
        },
        "metrics": metrics,
        "page_results": page_results,
        "live_queue_count": int(get_live_rfqs().get("count", 0) or 0),
        "browser_mode": bool(browser_mode),
        "scope": {
            "sprint": "Sprint 8C",
            "focus": "eTenders Connectivity Diagnostics",
            "notes": "Diagnostics only. No harvesting or governance changes.",
        },
    }

    diagnostics_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    _write_summary_md(summary_path, payload)

    return {
        "diagnostics": payload,
        "output_dir": str(output_root),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sprint 8C eTenders Connectivity Diagnostics")
    parser.add_argument("--pages", type=int, default=20, help="Number of pages to request")
    parser.add_argument("--limit", type=int, default=500, help="Maximum rows to cover across the requested pages")
    parser.add_argument("--timeout", type=int, default=20, help="Per-page request timeout in seconds")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_OUTPUT_DIR, help="Output directory for diagnostics artifacts")
    parser.add_argument("--browser-mode", action="store_true", help="Attempt browser-mode fetch and screenshot capture for each page")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_etenders_connectivity_diagnostics(
        pages=max(1, int(args.pages or 20)),
        limit=max(1, int(args.limit or 500)),
        timeout=max(1, int(args.timeout or 20)),
        output_dir=Path(args.output_dir),
        browser_mode=bool(args.browser_mode),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
