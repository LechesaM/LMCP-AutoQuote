from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlencode

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests

from app.core.runtime_paths import get_runtime_paths
from app.services.harvest_source_registry_service import CURATED_LIVE_SOURCE_FILE, load_harvest_sources
from app.services.live_rfq_store import get_live_rfqs


ETENDERS_BASE = "https://www.etenders.gov.za"
ETENDERS_OPPORTUNITIES = "https://www.etenders.gov.za/Home/opportunities"
ETENDERS_PAGINATED_ENDPOINT = "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities"
DEFAULT_OUTPUT_DIR = "runtime/harvest_recovery"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _page_plan(pages: int, limit: int) -> Tuple[int, int]:
    pages = max(1, int(pages or 1))
    limit = max(1, int(limit or 1))
    page_size = max(1, (limit + pages - 1) // pages)
    return pages, page_size


def _normalize_url(url: Any) -> str:
    text = _clean(url).lower()
    return text.rstrip("/")


def _detect_registry_paths() -> List[Path]:
    runtime_paths = get_runtime_paths()
    project_root = runtime_paths.project_root
    runtime_root = runtime_paths.runtime_root
    env_paths = [
        _clean(os.getenv("LMCP_HARVEST_SOURCE_REGISTRY_PATH")),
        _clean(os.getenv("HARVEST_SOURCE_REGISTRY_PATH")),
        _clean(os.getenv("LMCP_SOURCE_REGISTRY_PATH")),
    ]
    candidates = [Path(value).expanduser() for value in env_paths if value]
    candidates.extend(
        [
            project_root / "app" / "data" / "harvest_sources.json",
            project_root / "app" / "data" / "smoke_harvest_sources.json",
            runtime_root / "manual_production" / "harvest_sources.json",
            runtime_root / "manual_production" / "harvest_sources.jsonl",
        ]
    )
    return candidates


def _load_registry_sources() -> Tuple[List[Dict[str, Any]], str, List[str]]:
    checked: List[str] = []
    for path in _detect_registry_paths():
        checked.append(str(path))
        if not path.exists():
            continue
        try:
            return load_harvest_sources(path), str(path), checked
        except Exception:
            continue
    try:
        return load_harvest_sources(CURATED_LIVE_SOURCE_FILE), CURATED_LIVE_SOURCE_FILE, checked
    except Exception:
        return [], CURATED_LIVE_SOURCE_FILE, checked


def _select_etenders_sources(registry_sources: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    seen = set()
    for row in registry_sources:
        if not isinstance(row, dict):
            continue
        blob = " ".join(
            [
                _clean(row.get("name")),
                _clean(row.get("source_name")),
                _clean(row.get("url")),
                _clean(row.get("list_url")),
            ]
        ).lower()
        if "etender" not in blob and "national treasury" not in blob and "www.etenders.gov.za" not in blob:
            continue
        key = _normalize_url(row.get("url") or row.get("list_url")) or _clean(row.get("name") or row.get("source_name")).lower()
        if key in seen:
            continue
        seen.add(key)
        selected.append(row)
    return selected


def _build_page_params(start: int, length: int) -> Dict[str, str]:
    return {
        "draw": "1",
        "columns[0][data]": "",
        "columns[0][name]": "",
        "columns[0][searchable]": "true",
        "columns[0][orderable]": "false",
        "columns[0][search][value]": "",
        "columns[0][search][regex]": "false",
        "columns[1][data]": "category",
        "columns[1][name]": "",
        "columns[1][searchable]": "true",
        "columns[1][orderable]": "true",
        "columns[1][search][value]": "",
        "columns[1][search][regex]": "false",
        "columns[2][data]": "description",
        "columns[2][name]": "",
        "columns[2][searchable]": "true",
        "columns[2][orderable]": "false",
        "columns[2][search][value]": "",
        "columns[2][search][regex]": "false",
        "columns[3][data]": "eSubmission",
        "columns[3][name]": "",
        "columns[3][searchable]": "true",
        "columns[3][orderable]": "true",
        "columns[3][search][value]": "",
        "columns[3][search][regex]": "false",
        "columns[4][data]": "date_Published",
        "columns[4][name]": "",
        "columns[4][searchable]": "true",
        "columns[4][orderable]": "true",
        "columns[4][search][value]": "",
        "columns[4][search][regex]": "false",
        "columns[5][data]": "closing_Date",
        "columns[5][name]": "",
        "columns[5][searchable]": "true",
        "columns[5][orderable]": "true",
        "columns[5][search][value]": "",
        "columns[5][search][regex]": "false",
        "columns[6][data]": "actions",
        "columns[6][name]": "",
        "columns[6][searchable]": "true",
        "columns[6][orderable]": "true",
        "columns[6][search][value]": "",
        "columns[6][search][regex]": "false",
        "order[0][column]": "2",
        "order[0][dir]": "desc",
        "start": str(start),
        "length": str(length),
        "search[value]": "",
        "search[regex]": "false",
        "status": "1",
        "_": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
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


def _parse_rows(payload: Any) -> int:
    if isinstance(payload, dict):
        total = 0
        for key in ("data", "aaData", "results", "items", "rows", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                total += len(value)
        return total
    if isinstance(payload, list):
        return len(payload)
    return 0


def _fetch_page_diagnostics(
    page_url: str,
    *,
    timeout: int,
    browser_mode: bool = False,
    browser_screenshot_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    started = datetime.now(timezone.utc)
    raw_text = ""
    parsed_json = None
    response_length = 0
    status_code = 0
    final_url = page_url
    redirect_chain: List[Dict[str, Any]] = []
    exception_class = ""
    exception_message = ""
    page_rows = 0
    content_type = ""
    screenshot_path = ""
    fetch_mode = "requests"

    try:
        response = requests.get(page_url, timeout=timeout, allow_redirects=True, headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146 Safari/537.36"
            ),
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": ETENDERS_OPPORTUNITIES,
            "X-Requested-With": "XMLHttpRequest",
        })
        status_code = int(response.status_code or 0)
        final_url = _clean(response.url)
        content_type = _clean(response.headers.get("content-type", ""))
        redirect_chain = _extract_redirect_chain(response)
        raw_text = response.text or ""
        response_length = len(response.content or b"")
        try:
            parsed_json = response.json()
            page_rows = _parse_rows(parsed_json)
        except Exception:
            parsed_json = None
            page_rows = 0
        if browser_mode:
            fetch_mode = "browser"
    except Exception as exc:
        exception_class = exc.__class__.__name__
        exception_message = _clean(exc)

    if browser_mode:
        fetch_mode = "browser"
        try:
            from playwright.sync_api import sync_playwright  # type: ignore

            browser_screenshot_dir = browser_screenshot_dir or get_runtime_paths().runtime_root / "harvest_recovery" / "screenshots"
            browser_screenshot_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = str(browser_screenshot_dir / f"page_{hashlib.sha1(page_url.encode('utf-8')).hexdigest()[:12]}.png")
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(page_url, wait_until="domcontentloaded", timeout=max(timeout, 1) * 1000)
                page.screenshot(path=screenshot_path, full_page=True)
                final_url = _clean(page.url)
                content = page.content()
                response_length = len(content.encode("utf-8"))
                raw_text = content
                status_code = int(getattr(page, "status", 0) or status_code)
                browser.close()
        except Exception as exc:
            if not exception_class:
                exception_class = exc.__class__.__name__
                exception_message = _clean(exc)

    response_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest() if raw_text else ""
    page_status = "ok" if status_code and status_code < 400 and not exception_class else "failed"
    if status_code in {301, 302, 303, 307, 308}:
        page_status = "redirect"
    if exception_class and not status_code:
        page_status = "exception"

    return {
        "page_url": page_url,
        "fetch_mode": fetch_mode,
        "status": page_status,
        "http_status": status_code,
        "final_url": final_url,
        "redirect_chain": redirect_chain,
        "response_length": response_length,
        "response_hash": response_hash,
        "response_text_preview": raw_text[:2000],
        "response_json_present": parsed_json is not None,
        "response_rows": page_rows,
        "content_type": content_type,
        "exception_class": exception_class,
        "exception_message": exception_message[:500],
        "screenshot_path": screenshot_path,
        "elapsed_seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 3),
    }


def _write_summary_md(path: Path, payload: Dict[str, Any]) -> None:
    metrics = payload["metrics"]
    lines: List[str] = [
        "# Sprint 8B eTenders Fetch Diagnostics",
        "",
        f"Generated at: {payload['generated_at']}",
        "",
        "## Guardrails",
        "",
        f"- Portal submission disabled: `{payload['guardrails']['portal_submission_disabled']}`",
        f"- Human approval required: `{payload['guardrails']['human_approval_required']}`",
        f"- Autonomous submission enabled: `{payload['guardrails']['autonomous_submission_enabled']}`",
        "",
        "## Fetch Metrics",
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
        "redirecting_pages",
        "browser_mode_pages",
        "screenshot_count",
    ]:
        lines.append(f"| {key} | {metrics[key]} |")
    lines.extend(["", "## Failure Types", ""])
    for failure_type, count in metrics["top_failure_types"]:
        lines.append(f"- {failure_type}: {count}")
    lines.extend(["", "## Page Results", "", "| Page | HTTP | Status | Redirects | Bytes | Rows | Exception | Screenshot |", "| --- | ---: | --- | ---: | ---: | ---: | --- | --- |"])
    for row in payload["page_results"][:20]:
        lines.append(
            f"| {row['page_index']} | {row['http_status']} | {row['status']} | {len(row['redirect_chain'])} | {row['response_length']} | {row['response_rows']} | {row['exception_class'] or ''} | {row['screenshot_path'] or ''} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_etenders_fetch_diagnostics(
    *,
    pages: int = 20,
    limit: int = 500,
    timeout: int = 20,
    output_dir: Optional[Path] = None,
    browser_mode: bool = False,
    fetch_page_fn=_fetch_page_diagnostics,
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
    failure_counts: Dict[str, int] = {}

    for page_index in range(pages_requested):
        start = page_index * page_size
        page_url = f"{ETENDERS_PAGINATED_ENDPOINT}?{urlencode(_build_page_params(start, page_size))}"
        page = fetch_page_fn(
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
        if _clean(page.get("status")).lower() != "ok":
            pages_failed += 1
        else:
            pages_fetched += 1
        if len(page.get("redirect_chain") or []) > 1:
            redirecting_pages += 1
        if _clean(page.get("fetch_mode")).lower() == "browser":
            browser_mode_pages += 1
        if page.get("screenshot_path"):
            screenshot_count += 1
        key = page.get("exception_class") or page.get("status") or "unknown"
        failure_counts[key] = failure_counts.get(key, 0) + (0 if _clean(page.get("status")).lower() == "ok" else 1)

    metrics = {
        "pages_requested": pages_requested,
        "pages_fetched": pages_fetched,
        "pages_failed": pages_failed,
        "rows_seen": rows_seen,
        "response_bytes_total": response_bytes_total,
        "redirecting_pages": redirecting_pages,
        "browser_mode_pages": browser_mode_pages,
        "screenshot_count": screenshot_count,
        "top_failure_types": sorted(failure_counts.items(), key=lambda item: (-item[1], item[0])),
        "configured_sources": len(registry_sources),
        "etenders_sources": len(etenders_sources),
    }

    output_root = Path(output_dir) if output_dir else get_runtime_paths().runtime_root / "harvest_recovery"
    output_root.mkdir(parents=True, exist_ok=True)
    diagnostics_path = output_root / "fetch_diagnostics.json"
    summary_path = output_root / "fetch_diagnostics.md"

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
            "sprint": "Sprint 8B",
            "focus": "eTenders Fetch Diagnostics",
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
    parser = argparse.ArgumentParser(description="Sprint 8B eTenders Fetch Diagnostics")
    parser.add_argument("--pages", type=int, default=20, help="Number of pages to request")
    parser.add_argument("--limit", type=int, default=500, help="Maximum rows to cover across the requested pages")
    parser.add_argument("--timeout", type=int, default=20, help="Per-page request timeout in seconds")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_OUTPUT_DIR, help="Output directory for diagnostics artifacts")
    parser.add_argument("--browser-mode", action="store_true", help="Attempt browser-mode fetch and screenshot capture for each page")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_etenders_fetch_diagnostics(
        pages=max(1, int(args.pages or 20)),
        limit=max(1, int(args.limit or 500)),
        timeout=max(1, int(args.timeout or 20)),
        output_dir=Path(args.output_dir),
        browser_mode=bool(args.browser_mode),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
