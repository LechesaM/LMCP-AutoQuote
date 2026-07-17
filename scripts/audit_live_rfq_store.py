#!/usr/bin/env python3
"""Read-only Live RFQ Store recovery audit.

This utility inspects source code, runtime files, Docker metadata, logs, and
GET-only API endpoints. It intentionally avoids mutating HTTP methods and any
store rewrite.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import os
import re
import subprocess
import sys
import traceback
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


ENDPOINTS = [
    "/supply-command/live-rfqs",
    "/tender-pipeline/live-rfqs",
    "/tender-pipeline/filtered-live-rfqs",
    "/tender-pipeline/recommended-live-rfqs",
    "/tender-pipeline/scored-live-rfqs",
    "/revenue-dashboard/live-rfqs",
    "/api/rfq/recent",
    "/rfq-lifecycle/items",
]

ROUTE_TARGETS = [
    ("app/api/supply_command_api.py", "/live-rfqs", "/supply-command/live-rfqs"),
    ("app/api/tender_pipeline_api.py", "/live-rfqs", "/tender-pipeline/live-rfqs"),
    ("app/api/rfq_stable_api.py", "/recent", "/api/rfq/recent"),
    ("app/api/rfq_lifecycle_api.py", "/items", "/rfq-lifecycle/items"),
]

MINIMUM_INSPECT_FILES = [
    "app/api/supply_command_api.py",
    "app/api/tender_pipeline_api.py",
    "app/api/rfq_stable_api.py",
    "app/services/tender_harvester.py",
    "app/services/live_supply_pipeline.py",
    "app/services/harvest_to_opportunity.py",
    "app/services/harvester_adapter.py",
    "app/services/direct_portal_harvesters.py",
    "app/services/rfq_lifecycle_service.py",
]

IDENTIFIERS = [
    "LiveRfqStore",
    "LiveRFQStore",
    "live_rfq_store",
    "live_rfqs",
    "live-rfqs",
    "LIVE_RFQ",
    "upsert",
    "bulk_upsert",
    "write_text",
    "json.dump",
    "json.dumps",
    "runtime",
    "supply_command",
    "tender_pipeline",
    "harvest",
    "acquisition",
]

WRITE_MARKERS = [
    "upsert_live_rfq",
    "upsert_rfq",
    "save_live_rfq",
    "save_live_rfqs",
    "persist_live_rfq",
    "promote_rfq_to_live_store",
    "promote_live_rfqs",
    "append_live_rfq",
    "append_live_rfqs",
    "replace_live_rfqs",
    "clear_live_rfqs",
    "LIVE_RFQ_STORE_PATH.write_text",
    "live_rfqs.json",
]

HARVEST_MARKERS = ["harvest", "acquisition", "candidate", "opportunit", "discovery", "rfq"]
TIMESTAMP_KEYS = [
    "updated_at",
    "created_at",
    "harvested_at",
    "last_harvested_at",
    "published_at",
    "publication_date",
    "timestamp",
    "run_started_at",
    "generated_at",
]
CLOSING_KEYS = ["closing_at", "closing_date", "deadline", "submission_deadline", "bid_closing_date"]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_from_epoch(epoch: float) -> str:
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).isoformat()


def parse_time(value: Any) -> Optional[dt.datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return dt.datetime.fromtimestamp(float(value), dt.timezone.utc)
        except Exception:
            return None
    text = str(value).strip()
    if not text:
        return None
    candidates = [text]
    if text.endswith("Z"):
        candidates.append(text[:-1] + "+00:00")
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        candidates.append(text + "T00:00:00+00:00")
    for candidate in candidates:
        try:
            parsed = dt.datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.astimezone(dt.timezone.utc)
        except Exception:
            pass
    for fmt in ("%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(text[:19], fmt).replace(tzinfo=dt.timezone.utc)
        except Exception:
            pass
    return None


def safe_rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


def read_text(path: Path, limit: Optional[int] = None) -> Tuple[Optional[str], Optional[str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if limit is not None:
            text = text[:limit]
        return text, None
    except Exception as exc:
        return None, str(exc)


def run_cmd(args: List[str], cwd: Path, timeout: int = 12) -> Dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
            "command": args,
        }
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc), "command": args}
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "error": "timeout", "stdout": exc.stdout, "stderr": exc.stderr, "command": args}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "command": args}


def get_git(root: Path) -> Dict[str, Any]:
    branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], root)
    commit = run_cmd(["git", "rev-parse", "HEAD"], root)
    status = run_cmd(["git", "status", "--porcelain"], root)
    return {
        "branch": branch.get("stdout", "") if branch.get("ok") else "",
        "commit": commit.get("stdout", "") if commit.get("ok") else "",
        "working_tree_clean": bool(status.get("ok") and not status.get("stdout")),
        "errors": [row for row in (branch, commit, status) if not row.get("ok")],
    }


def http_get_json(base_url: str, path: str, timeout: int = 5) -> Dict[str, Any]:
    url = base_url.rstrip("/") + path
    try:
        req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read(5_000_000)
            text = body.decode("utf-8", errors="replace")
            try:
                payload = json.loads(text)
            except Exception as exc:
                return {"http_status": response.status, "error": "malformed_json: %s" % exc, "raw_sample": text[:500]}
            return endpoint_summary(payload, response.status)
    except urllib.error.HTTPError as exc:
        return {"http_status": exc.code, "error": str(exc)}
    except Exception as exc:
        return {"http_status": None, "error": str(exc)}


def extract_items(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("items", "rfqs", "recent", "opportunities", "results", "documents", "eligible_items", "qualified_candidates"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict):
            return [row for row in value.values() if isinstance(row, dict)]
    nested = payload.get("data")
    if nested is not payload:
        return extract_items(nested)
    return []


def latest_value(items: Iterable[Dict[str, Any]], keys: List[str]) -> Optional[str]:
    latest: Optional[dt.datetime] = None
    raw = None
    for item in items:
        for key in keys:
            parsed = parse_time(item.get(key))
            if parsed and (latest is None or parsed > latest):
                latest = parsed
                raw = item.get(key)
    return str(raw) if raw is not None else None


def endpoint_summary(payload: Any, status: int) -> Dict[str, Any]:
    items = extract_items(payload)
    sample_ids = []
    for item in items[:10]:
        for key in ("rfq_id", "id", "buyer_rfq_number", "rfq_number", "reference_number", "title"):
            if item.get(key):
                sample_ids.append(str(item.get(key)))
                break
    source_fields: Dict[str, Any] = {}
    if items:
        keys = sorted({key for item in items[:5] for key in item.keys()})
        source_fields = {
            "sample_keys": keys[:80],
            "has_documents": any(bool(item.get("documents") or item.get("document_urls") or item.get("downloaded_files")) for item in items),
            "has_boq": any(bool(item.get("boq") or item.get("boq_items") or item.get("line_items") or item.get("items")) for item in items),
            "has_pricing": any(bool(item.get("pricing") or item.get("pricing_result") or item.get("pricing_schedule")) for item in items),
        }
    return {
        "http_status": status,
        "count": len(items),
        "latest_closing_date": latest_value(items, CLOSING_KEYS),
        "latest_record_timestamp": latest_value(items, TIMESTAMP_KEYS),
        "sample_ids": sample_ids,
        "source_fields": source_fields,
    }


def decorator_path(deco: ast.AST) -> Optional[str]:
    if not isinstance(deco, ast.Call):
        return None
    func = deco.func
    attr = func.attr if isinstance(func, ast.Attribute) else ""
    if attr not in {"get", "post", "put", "patch", "delete"}:
        return None
    if deco.args and isinstance(deco.args[0], ast.Constant):
        return str(deco.args[0].value)
    return None


def inspect_route_file(root: Path, rel: str, route_path: str, endpoint: str) -> Dict[str, Any]:
    path = root / rel
    row: Dict[str, Any] = {"endpoint": endpoint, "source_file": rel, "route_path": route_path, "exists": path.exists()}
    text, err = read_text(path)
    if err:
        row["error"] = err
        return row
    try:
        tree = ast.parse(text or "")
    except Exception as exc:
        row["error"] = "ast_parse_failed: %s" % exc
        return row
    calls: List[str] = []
    imports: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append((ast.get_source_segment(text or "", node) or "").strip())
        if isinstance(node, ast.FunctionDef):
            paths = [decorator_path(deco) for deco in node.decorator_list]
            if route_path in paths:
                row.update({"function": node.name, "line": node.lineno})
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        seg = ast.get_source_segment(text or "", child)
                        if seg:
                            calls.append(seg.split("\n")[0][:180])
    row["imports"] = [line for line in imports if "live_rfq_store" in line or "rfq_lifecycle" in line or "self_healing_harvester" in line][:20]
    row["calls"] = calls[:30]
    row["evidence"] = infer_route_storage(row)
    return row


def infer_route_storage(row: Dict[str, Any]) -> List[str]:
    evidence: List[str] = []
    joined = " ".join(row.get("imports", []) + row.get("calls", []))
    if "app.services.live_rfq_store" in joined or "LiveRFQStore" in joined:
        evidence.append("Uses app.services.live_rfq_store.LiveRFQStore, which is backed by runtime/live_rfqs.json in active source.")
    if "self_healing_harvester" in joined or "get_live_rfqs_for_api" in joined:
        evidence.append("Calls self_healing_harvester.get_live_rfqs_for_api; verify whether that delegates to the same live store.")
    if "rfq_lifecycle" in joined or "service().list_items" in joined:
        evidence.append("Uses RFQ lifecycle service; active lifecycle store is inspected separately.")
    if "_load_runtime_records" in joined:
        evidence.append("Loads recent RFQs from rfq_stable_api runtime source directories.")
    return evidence


def inspect_routes(root: Path) -> List[Dict[str, Any]]:
    return [inspect_route_file(root, rel, route_path, endpoint) for rel, route_path, endpoint in ROUTE_TARGETS]


def stat_json_candidate(root: Path, path: Path) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "host_path": str(path.resolve()),
        "relative_path": safe_rel(path, root),
        "container_path": "/app/" + safe_rel(path, root) if safe_rel(path, root) != str(path) else None,
        "type": "JSON file" if path.suffix.lower() == ".json" else "runtime file",
        "exists": path.exists(),
    }
    try:
        st = path.stat()
        row.update({"size_bytes": st.st_size, "modified_at": iso_from_epoch(st.st_mtime)})
    except Exception as exc:
        row["error"] = str(exc)
        return row
    if path.suffix.lower() == ".json" and st.st_size <= 20_000_000:
        text, err = read_text(path)
        if err:
            row["parse_error"] = err
        else:
            try:
                payload = json.loads(text or "")
                items = extract_items(payload)
                row["record_count"] = len(items)
                row["latest_record_timestamp"] = latest_value(items, TIMESTAMP_KEYS)
                row["latest_closing_date"] = latest_value(items, CLOSING_KEYS)
                if isinstance(payload, dict):
                    row["top_level_keys"] = sorted(payload.keys())[:40]
            except Exception as exc:
                row["parse_error"] = str(exc)
    return row


def likely_runtime_files(root: Path) -> List[Path]:
    paths: List[Path] = []
    for base in (root / "runtime", root / "app" / "runtime"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel = safe_rel(path, root).lower()
            name = path.name.lower()
            if path.suffix.lower() in {".json", ".jsonl", ".sqlite", ".sqlite3", ".db", ".txt", ".log"} and any(
                token in rel for token in ("rfq", "harvest", "candidate", "opportunit", "discovery", "acquisition", "tender")
            ):
                paths.append(path)
    explicit = [
        root / "runtime" / "live_rfqs.json",
        root / "runtime" / "live_harvested_rfqs.json",
        root / "runtime" / "rfq_lifecycle" / "rfqs.json",
        root / "runtime" / "multi_portal_discovery" / "qualified_candidates_report.json",
        root / "runtime" / "multi_portal_discovery" / "eligible_candidates_report.json",
        root / "runtime" / "opportunity_extraction" / "high_confidence_opportunities.json",
    ]
    for path in explicit:
        if path.exists() and path not in paths:
            paths.append(path)
    return sorted(set(paths), key=lambda p: (p.name != "live_rfqs.json", str(p)))[:300]


def inspect_store_candidates(root: Path) -> List[Dict[str, Any]]:
    return [stat_json_candidate(root, path) for path in likely_runtime_files(root)]


def active_store_from_candidates(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    for row in candidates:
        if row.get("relative_path") == "runtime/live_rfqs.json":
            active = dict(row)
            active["evidence"] = [
                "app/services/live_rfq_store.py defines LIVE_RFQ_STORE_PATH = PROJECT_ROOT / 'runtime' / 'live_rfqs.json'.",
                "GET /tender-pipeline/live-rfqs calls LiveRFQStore.get_all().",
                "GET /supply-command/live-rfqs imports the same module and also calls self_healing_harvester.get_live_rfqs_for_api.",
            ]
            return active
    return {"type": "unknown", "evidence": ["runtime/live_rfqs.json was not found among candidates."]}


def find_source_references(root: Path) -> Dict[str, Any]:
    py_files = [path for path in (root / "app").rglob("*.py") if path.is_file()]
    writers: List[Dict[str, Any]] = []
    producers_elsewhere: List[Dict[str, Any]] = []
    p_imports: List[Dict[str, Any]] = []
    for path in py_files:
        text, err = read_text(path)
        if err or text is None:
            continue
        rel = safe_rel(path, root)
        lines = text.splitlines()
        if "live_rfq_store.p" in text:
            p_imports.append({"file": rel, "line": text[: text.find("live_rfq_store.p")].count("\n") + 1})
        if "live_rfq_store" in text or "live_rfqs.json" in text or "LiveRFQStore" in text:
            hits = []
            for i, line in enumerate(lines, 1):
                if any(marker in line for marker in WRITE_MARKERS):
                    hits.append({"line": i, "text": line.strip()[:220]})
            if hits:
                writers.append({"file": rel, "hits": hits[:30]})
        lower = text.lower()
        if any(marker in lower for marker in HARVEST_MARKERS) and ("write_text" in text or "json.dump" in text or "json.dumps" in text):
            destinations = []
            for i, line in enumerate(lines, 1):
                if ("write_text" in line or "json.dump" in line or "json.dumps" in line) and "live_rfqs.json" not in line:
                    destinations.append({"line": i, "text": line.strip()[:220]})
            if destinations:
                producers_elsewhere.append({"file": rel, "write_destinations": destinations[:30]})
    return {"writers": writers, "producers_elsewhere": producers_elsewhere, "p_imports": p_imports}


def inspect_live_rfq_store_p(root: Path, refs: Dict[str, Any]) -> Dict[str, Any]:
    py = root / "app" / "services" / "live_rfq_store.py"
    p = root / "app" / "services" / "live_rfq_store.p"
    result = {
        "path": str(p.resolve()) if p.exists() else str(p),
        "exists": p.exists(),
        "actively_imported": False,
        "classification": "missing",
        "evidence": [],
    }
    if p.exists():
        result["classification"] = "abandoned_or_recovered_source_file"
        result["evidence"].append(".p is not a standard Python source suffix for app.services.live_rfq_store imports.")
        if py.exists():
            result["evidence"].append("app/services/live_rfq_store.py exists and wins normal import resolution.")
        if refs.get("p_imports"):
            result["actively_imported"] = True
            result["classification"] = "referenced_by_source"
            result["evidence"].append("Source text references live_rfq_store.p explicitly.")
    return result


def inspect_compose(root: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in sorted(root.glob("*compose*.yml")) + sorted(root.glob("*compose*.yaml")):
        text, err = read_text(path)
        row: Dict[str, Any] = {"file": safe_rel(path, root), "exists": path.exists()}
        if err:
            row["error"] = err
            rows.append(row)
            continue
        mounts = []
        current_service = None
        for line in (text or "").splitlines():
            svc_match = re.match(r"^  ([A-Za-z0-9_.-]+):\s*$", line)
            if svc_match:
                current_service = svc_match.group(1)
            if current_service and re.match(r"^\s+-\s+.*:.*", line):
                mounts.append({"service": current_service, "spec": line.strip()[2:].strip()})
        row["mounts"] = mounts
        rows.append(row)
    return rows


def inspect_docker(root: Path, container: str, log_hours: int) -> Dict[str, Any]:
    result: Dict[str, Any] = {"container": container, "available": False, "mounts": [], "errors": []}
    inspect = run_cmd(["docker", "inspect", container], root, timeout=10)
    if not inspect.get("ok"):
        result["errors"].append(inspect)
        return result
    result["available"] = True
    try:
        data = json.loads(inspect.get("stdout") or "[]")
        if data:
            state = data[0].get("State", {})
            result["running"] = bool(state.get("Running"))
            for mount in data[0].get("Mounts", []):
                result["mounts"].append(
                    {
                        "type": mount.get("Type"),
                        "source": mount.get("Source"),
                        "destination": mount.get("Destination"),
                        "name": mount.get("Name"),
                        "rw": mount.get("RW"),
                    }
                )
    except Exception as exc:
        result["errors"].append({"error": "docker inspect JSON parse failed: %s" % exc})
    for args, key in [
        (["docker", "exec", container, "readlink", "-f", "/app/runtime/live_rfqs.json"], "container_live_store_realpath"),
        (["docker", "exec", container, "sh", "-lc", "test -f /app/runtime/live_rfqs.json && stat -c '%s %Y %n' /app/runtime/live_rfqs.json || true"], "container_live_store_stat"),
    ]:
        row = run_cmd(args, root, timeout=10)
        result[key] = row.get("stdout") if row.get("ok") else None
        if not row.get("ok"):
            result["errors"].append(row)
    worker_names = ["lmcp-acquisition-worker", "lmcp-beat", "lmcp-celery-beat", "lmcp-worker"]
    result["logs"] = {}
    since = "%dh" % int(log_hours)
    for name in worker_names:
        logs = run_cmd(["docker", "logs", "--since", since, "--tail", "400", name], root, timeout=15)
        result["logs"][name] = {
            "ok": logs.get("ok"),
            "stdout_tail": (logs.get("stdout") or "")[-12000:],
            "stderr_tail": (logs.get("stderr") or "")[-4000:],
            "error": logs.get("error"),
        }
    return result


def summarize_worker(docker_info: Dict[str, Any], candidates: List[Dict[str, Any]], now: dt.datetime) -> Dict[str, Any]:
    logs = docker_info.get("logs", {}) if isinstance(docker_info, dict) else {}
    acquisition_log = logs.get("lmcp-acquisition-worker", {})
    text = (acquisition_log.get("stdout_tail") or "") + "\n" + (acquisition_log.get("stderr_tail") or "")
    last_error = ""
    for line in reversed(text.splitlines()):
        if re.search(r"\b(error|exception|traceback|failed)\b", line, re.I):
            last_error = line[-500:]
            break
    last_success = ""
    for line in reversed(text.splitlines()):
        if re.search(r"\b(succeeded|success|harvest|acquisition|written|ingested)\b", line, re.I):
            last_success = line[-500:]
            break
    windows = {"24_hours": 0, "7_days": 0, "30_days": 0}
    destinations = []
    for row in candidates:
        rel = row.get("relative_path", "")
        if not any(token in rel.lower() for token in ("rfq", "harvest", "candidate", "acquisition", "opportunit", "discovery")):
            continue
        parsed = parse_time(row.get("modified_at"))
        if not parsed:
            continue
        age = now - parsed
        if age <= dt.timedelta(hours=24):
            windows["24_hours"] += 1
        if age <= dt.timedelta(days=7):
            windows["7_days"] += 1
        if age <= dt.timedelta(days=30):
            windows["30_days"] += 1
        if age <= dt.timedelta(days=30):
            destinations.append({"path": rel, "modified_at": row.get("modified_at"), "record_count": row.get("record_count")})
    return {
        "container": "lmcp-acquisition-worker",
        "running": bool(acquisition_log.get("ok")),
        "last_successful_activity": last_success,
        "last_error": last_error,
        "write_destinations": destinations[:40],
        "recent_file_write_counts": windows,
    }


def detect_mismatches(
    endpoint_results: Dict[str, Any],
    active_store: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    docker_info: Dict[str, Any],
    refs: Dict[str, Any],
) -> List[Dict[str, Any]]:
    mismatches: List[Dict[str, Any]] = []
    supply_count = endpoint_results.get("/supply-command/live-rfqs", {}).get("count")
    tender_count = endpoint_results.get("/tender-pipeline/live-rfqs", {}).get("count")
    store_count = active_store.get("record_count")
    if supply_count is not None and tender_count is not None and supply_count != tender_count:
        mismatches.append({"type": "ENDPOINT_COUNT_MISMATCH", "evidence": "supply-command count %s != tender-pipeline count %s" % (supply_count, tender_count)})
    if store_count is not None and tender_count is not None and int(store_count or 0) != int(tender_count or 0):
        mismatches.append({"type": "ENDPOINT_STORE_COUNT_MISMATCH", "evidence": "runtime/live_rfqs.json count %s != tender-pipeline endpoint count %s" % (store_count, tender_count)})
    live_mtime = parse_time(active_store.get("modified_at"))
    now = utc_now()
    if live_mtime and now - live_mtime > dt.timedelta(days=30):
        mismatches.append({"type": "STORE_STALE", "evidence": "runtime/live_rfqs.json modified_at %s is older than 30 days" % active_store.get("modified_at")})
    fresh_elsewhere = [
        row for row in candidates
        if row.get("relative_path") != "runtime/live_rfqs.json"
        and parse_time(row.get("modified_at"))
        and now - parse_time(row.get("modified_at")) <= dt.timedelta(days=30)
        and int(row.get("record_count") or 0) > 0
    ]
    if fresh_elsewhere and (not live_mtime or now - live_mtime > dt.timedelta(days=7)):
        mismatches.append({"type": "ACQUISITION_WRITES_ELSEWHERE", "evidence": "Fresh RFQ-like runtime files exist while live store is stale.", "examples": fresh_elsewhere[:10]})
    mounts = docker_info.get("mounts") or []
    runtime_mounts = [m for m in mounts if m.get("destination") == "/app/runtime"]
    app_mounts = [m for m in mounts if m.get("destination") == "/app"]
    if mounts and not runtime_mounts and not app_mounts:
        mismatches.append({"type": "CONTAINER_VOLUME_MISMATCH", "evidence": "Docker inspect did not show bind mount for /app or /app/runtime."})
    for writer in refs.get("writers", []):
        if writer.get("file") == "app/api/tender_pipeline_api.py":
            for hit in writer.get("hits", []):
                if "LiveRFQStore.upsert_rfq(item)" in hit.get("text", ""):
                    mismatches.append({"type": "PRODUCER_PATH_BUG", "evidence": "tender_pipeline_api multi-result branch references undefined item when persisting live store.", "file": writer.get("file"), "line": hit.get("line")})
    return mismatches


def classify(endpoint_results: Dict[str, Any], active_store: Dict[str, Any], worker: Dict[str, Any], mismatches: List[Dict[str, Any]]) -> Tuple[str, str]:
    types = {row.get("type") for row in mismatches}
    if "CONTAINER_VOLUME_MISMATCH" in types:
        return "CONTAINER_VOLUME_MISMATCH", "Confirm API and workers mount the same host runtime path before changing code."
    if "ACQUISITION_WRITES_ELSEWHERE" in types:
        return "ACQUISITION_WRITES_ELSEWHERE", "Bridge the active acquisition output into the Live RFQ Store with a narrow read-transform-upsert path after reviewing candidate examples."
    if "PRODUCER_PATH_BUG" in types:
        return "PRODUCER_PATH_MISMATCH", "Fix only the broken producer call site so it upserts the constructed live-store item."
    if "STORE_STALE" in types:
        recent = worker.get("recent_file_write_counts", {})
        if not recent.get("24_hours") and not recent.get("7_days"):
            return "ACQUISITION_NOT_RUNNING", "Restart or schedule acquisition only after confirming the intended queue and no mutating recovery endpoint is needed."
        return "STORE_STALE", "Trace the active producer into runtime/live_rfqs.json and repair the missing live-store promotion path."
    if int(active_store.get("record_count") or 0) == 0:
        return "CURRENT_DATA_NOT_AVAILABLE", "No current live-store data is available; inspect acquisition source health before repopulating anything."
    return "INCONCLUSIVE", "Review route implementations, Docker mounts, and producer candidates in the report before applying a repair."


def inspect_identifier_hits(root: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    files = [root / rel for rel in MINIMUM_INSPECT_FILES]
    files.extend(sorted((root / "app" / "services").glob("live_rfq_store*")))
    for path in files:
        rel = safe_rel(path, root)
        if not path.exists():
            rows.append({"file": rel, "exists": False})
            continue
        text, err = read_text(path)
        if err or text is None:
            rows.append({"file": rel, "exists": True, "error": err})
            continue
        hits = []
        for i, line in enumerate(text.splitlines(), 1):
            if any(identifier in line for identifier in IDENTIFIERS):
                hits.append({"line": i, "text": line.strip()[:220]})
        rows.append({"file": rel, "exists": True, "hits": hits[:80]})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only audit of Live RFQ Store recovery state.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--output", default="")
    parser.add_argument("--container", default="lmcp-api")
    parser.add_argument("--log-hours", type=int, default=168)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    now = utc_now()
    errors: List[Dict[str, Any]] = []

    def note(message: str) -> None:
        if args.verbose:
            print(message, file=sys.stderr)

    try:
        note("Inspecting GET endpoints")
        endpoint_results = {path: http_get_json(args.base_url, path) for path in ENDPOINTS}
        note("Inspecting route implementations")
        route_implementations = inspect_routes(root)
        note("Inspecting runtime store candidates")
        store_candidates = inspect_store_candidates(root)
        active_store = active_store_from_candidates(store_candidates)
        note("Inspecting source producers")
        refs = find_source_references(root)
        live_rfq_store_p = inspect_live_rfq_store_p(root, refs)
        note("Inspecting compose and Docker")
        compose = inspect_compose(root)
        docker_info = inspect_docker(root, args.container, args.log_hours)
        docker_mounts = docker_info.get("mounts", [])
        worker = summarize_worker(docker_info, store_candidates, now)
        mismatches = detect_mismatches(endpoint_results, active_store, store_candidates, docker_info, refs)
        classification, recommended = classify(endpoint_results, active_store, worker, mismatches)
        report: Dict[str, Any] = {
            "generated_at": now.isoformat(),
            "repository": str(root),
            "git": get_git(root),
            "endpoint_results": endpoint_results,
            "route_implementations": route_implementations,
            "store_candidates": store_candidates,
            "active_store": active_store,
            "live_rfq_store_p": live_rfq_store_p,
            "producer_candidates": refs.get("writers", []),
            "acquisition_producers_writing_elsewhere": refs.get("producers_elsewhere", []),
            "identifier_hits": inspect_identifier_hits(root),
            "compose": compose,
            "docker": docker_info,
            "docker_mounts": docker_mounts,
            "acquisition_worker": worker,
            "mismatches": mismatches,
            "classification": classification,
            "recommended_next_action": recommended,
            "errors": errors,
            "safety": {
                "mutating_requests_sent": False,
                "files_modified": False,
                "stores_modified": False,
                "http_methods_used": ["GET"],
                "prohibited_endpoints_called": [],
            },
        }
    except Exception as exc:
        report = {
            "generated_at": now.isoformat(),
            "repository": str(root),
            "classification": "INCONCLUSIVE",
            "recommended_next_action": "Audit failed before completion; inspect errors.",
            "errors": [{"error": str(exc), "traceback": traceback.format_exc()}],
            "safety": {"mutating_requests_sent": False, "files_modified": False, "stores_modified": False},
        }

    output_text = json.dumps(report, indent=2, sort_keys=True, default=str)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text + "\n", encoding="utf-8")
        note("Wrote report to %s" % output_path)
    else:
        print(output_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
