import json
import time
import socket
import concurrent.futures
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

try:
    from app.services.portal_registry import get_portal_registry
except Exception:
    get_portal_registry = None


CONNECT_TIMEOUT = 8
READ_TIMEOUT = 20
SLOW_THRESHOLD_SECONDS = 6.0
MAX_WORKERS = 60
OUTPUT_FILE = "portal_radar_report.json"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _normalize_portal(item: Any) -> Dict[str, Any]:
    if isinstance(item, str):
        return {
            "name": item,
            "url": item,
            "method": "GET",
            "headers": {},
        }

    return {
        "name": item.get("name") or item.get("portal_name") or item.get("url") or "unknown",
        "url": item.get("url") or item.get("base_url") or item.get("endpoint"),
        "method": (item.get("method") or "GET").upper(),
        "headers": item.get("headers") or {},
    }


def _fallback_registry() -> List[Dict[str, Any]]:
    return [
        {"name": "eTenders", "url": "https://www.etenders.gov.za/", "method": "GET", "headers": {}},
        {"name": "Tender Bulletin", "url": "https://www.tenderbulletins.co.za/", "method": "GET", "headers": {}},
    ]


def load_portals() -> List[Dict[str, Any]]:
    raw: List[Any] = []

    if get_portal_registry:
        try:
            registry = get_portal_registry()
            if isinstance(registry, list):
                raw = registry
            elif isinstance(registry, dict):
                raw = registry.get("portals", [])
        except Exception:
            raw = []

    if not raw:
        raw = _fallback_registry()

    portals = [_normalize_portal(item) for item in raw]
    portals = [p for p in portals if p.get("url")]
    return portals


def classify_result(
    status_code: Optional[int],
    elapsed: float,
    error_text: str = "",
) -> str:
    error_lower = (error_text or "").lower()

    if "403" in error_lower or "forbidden" in error_lower:
        return "blocked"
    if "429" in error_lower or "too many requests" in error_lower:
        return "blocked"
    if "captcha" in error_lower or "access denied" in error_lower:
        return "blocked"
    if status_code in (401, 403, 429):
        return "blocked"
    if status_code is None:
        return "broken"
    if status_code >= 500:
        return "broken"
    if elapsed >= SLOW_THRESHOLD_SECONDS:
        return "slow"
    if 200 <= status_code < 400:
        return "healthy"
    return "broken"


def probe_portal(portal: Dict[str, Any]) -> Dict[str, Any]:
    name = portal["name"]
    url = portal["url"]
    method = portal.get("method", "GET")
    headers = portal.get("headers", {})

    started = time.perf_counter()
    status_code = None
    error_text = ""
    resolved_ip = None

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if hostname:
            try:
                resolved_ip = socket.gethostbyname(hostname)
            except Exception:
                resolved_ip = None

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            allow_redirects=True,
        )
        elapsed = round(time.perf_counter() - started, 2)
        status_code = response.status_code

        response_text = (response.text or "")[:500].lower()
        if response.status_code in (401, 403, 429) or "captcha" in response_text or "access denied" in response_text:
            category = "blocked"
        else:
            category = classify_result(status_code, elapsed)

        return {
            "name": name,
            "url": url,
            "ip": resolved_ip,
            "status_code": status_code,
            "response_time_seconds": elapsed,
            "category": category,
            "error": "",
        }

    except requests.exceptions.Timeout as exc:
        elapsed = round(time.perf_counter() - started, 2)
        error_text = f"timeout: {exc}"
        return {
            "name": name,
            "url": url,
            "ip": resolved_ip,
            "status_code": status_code,
            "response_time_seconds": elapsed,
            "category": "slow",
            "error": error_text,
        }

    except requests.exceptions.RequestException as exc:
        elapsed = round(time.perf_counter() - started, 2)
        error_text = str(exc)
        category = classify_result(status_code, elapsed, error_text)
        return {
            "name": name,
            "url": url,
            "ip": resolved_ip,
            "status_code": status_code,
            "response_time_seconds": elapsed,
            "category": category,
            "error": error_text,
        }

    except Exception as exc:
        elapsed = round(time.perf_counter() - started, 2)
        return {
            "name": name,
            "url": url,
            "ip": resolved_ip,
            "status_code": status_code,
            "response_time_seconds": elapsed,
            "category": "broken",
            "error": f"unexpected error: {exc}",
        }


def run_parallel_diagnostic(portals: List[Dict[str, Any]]) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    started = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(probe_portal, portal): portal for portal in portals}

        for future in concurrent.futures.as_completed(future_map):
            try:
                results.append(future.result())
            except Exception as exc:
                portal = future_map[future]
                results.append(
                    {
                        "name": portal["name"],
                        "url": portal["url"],
                        "ip": None,
                        "status_code": None,
                        "response_time_seconds": 0,
                        "category": "broken",
                        "error": f"executor failure: {exc}",
                    }
                )

    duration = round(time.perf_counter() - started, 2)

    summary = {
        "healthy": sum(1 for x in results if x["category"] == "healthy"),
        "slow": sum(1 for x in results if x["category"] == "slow"),
        "broken": sum(1 for x in results if x["category"] == "broken"),
        "blocked": sum(1 for x in results if x["category"] == "blocked"),
    }

    slowest = sorted(results, key=lambda x: x["response_time_seconds"], reverse=True)[:20]

    return {
        "generated_at": _now(),
        "total_portals": len(results),
        "scan_duration_seconds": duration,
        "summary": summary,
        "slowest_20": slowest,
        "results": sorted(results, key=lambda x: (x["category"], -x["response_time_seconds"], x["name"])),
    }


def print_report(report: Dict[str, Any]) -> None:
    summary = report["summary"]

    print("\n" + "=" * 90)
    print("NATIONAL PROCUREMENT RADAR DIAGNOSTIC")
    print("=" * 90)
    print(f"Generated at : {report['generated_at']}")
    print(f"Total portals: {report['total_portals']}")
    print(f"Scan time    : {report['scan_duration_seconds']} sec")
    print("-" * 90)
    print(
        f"HEALTHY: {summary['healthy']} | "
        f"SLOW: {summary['slow']} | "
        f"BROKEN: {summary['broken']} | "
        f"BLOCKED: {summary['blocked']}"
    )
    print("-" * 90)

    for row in report["results"]:
        print(
            f"[{row['category'].upper():7}] "
            f"{str(row['status_code'] or '-'):>3}  "
            f"{row['response_time_seconds']:>5}s  "
            f"{row['name']}  ->  {row['url']}"
        )

    print("=" * 90)
    print(f"Saved report to: {OUTPUT_FILE}")
    print("=" * 90 + "\n")


def save_report(report: Dict[str, Any]) -> None:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def main() -> None:
    portals = load_portals()
    if not portals:
        print("No portals found in registry.")
        return

    report = run_parallel_diagnostic(portals)
    save_report(report)
    print_report(report)


if __name__ == "__main__":
    main()
