#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "runtime"
AUDIT_DIR = RUNTIME_DIR / "audit_trail"
CENTRAL_AUDIT_FILE = AUDIT_DIR / "audit_events.json"
QUOTE_COMPILATION_DIR = RUNTIME_DIR / "quote_compilation"
BACKUP_DIR = AUDIT_DIR / "probe_backups"
BASELINE_FILE = BACKUP_DIR / "audit_probe_baseline.json"
SEARCH_TERMS = [
    "2026-06-18",
    "Mark Reviewed Locally",
    "Hold Submission Candidate",
    "Ready for Operator Approval",
    "Approve for Quote Prep",
    "QUOTE_PACK_READY",
    "operator",
    "binder",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def make_backup(source: Path) -> Path | None:
    if not source.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{source.stem}.{utc_now_stamp()}{source.suffix}"
    shutil.copy2(source, backup_path)
    return backup_path


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def scan_pack_local_audit_files() -> list[Path]:
    if not QUOTE_COMPILATION_DIR.exists():
        return []
    return sorted(QUOTE_COMPILATION_DIR.rglob("audit_trail.jsonl"))


def file_metadata(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    stat = path.stat()
    return {
        "path": relative(path),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "sha256": sha256_bytes(data),
        "line_count": len(text.splitlines()),
    }


def central_event_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    if isinstance(raw, list):
        return len([item for item in raw if isinstance(item, dict)])
    return 0


def read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def latest_events(events: list[dict[str, Any]], limit: int = 30) -> list[dict[str, Any]]:
    return sorted(events, key=lambda item: str(item.get("created_at", "")), reverse=True)[:limit]


def compact_event(event: dict[str, Any]) -> str:
    created_at = str(event.get("created_at", ""))
    event_type = str(event.get("event_type", ""))
    title = str(event.get("title", ""))
    message = str(event.get("message", ""))
    buyer_rfq = str(event.get("buyer_rfq_number", ""))
    quote_number = str(event.get("quote_number", ""))
    payload = event.get("payload")
    payload_keys = ", ".join(sorted(payload.keys())) if isinstance(payload, dict) else ""
    return (
        f"- {created_at} | event_type={event_type or '-'} | title={title or '-'} "
        f"| rfq={buyer_rfq or '-'} | quote={quote_number or '-'} | message={message or '-'} "
        f"| payload_keys={payload_keys or '-'}"
    )


def contains_search_term(text: str) -> list[str]:
    lower_text = text.lower()
    return [term for term in SEARCH_TERMS if term.lower() in lower_text]


def matching_lines(text: str, limit: int = 20) -> list[str]:
    hits: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        lower_line = line.lower()
        matched = [term for term in SEARCH_TERMS if term.lower() in lower_line]
        if matched:
            preview = line.strip()
            if len(preview) > 240:
                preview = preview[:237] + "..."
            hits.append(f"{line_number}: {preview} | terms={', '.join(matched)}")
        if len(hits) >= limit:
            break
    return hits


def matching_central_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events:
        blob = json.dumps(event, ensure_ascii=True, sort_keys=True)
        matched_terms = contains_search_term(blob)
        if not matched_terms:
            continue
        rows.append(
            {
                "created_at": str(event.get("created_at", "")),
                "event_type": str(event.get("event_type", "")),
                "title": str(event.get("title", "")),
                "message": str(event.get("message", "")),
                "buyer_rfq_number": str(event.get("buyer_rfq_number", "")),
                "quote_number": str(event.get("quote_number", "")),
                "matched_terms": matched_terms,
                "event_hash": sha256_text(blob),
            }
        )
    return sorted(rows, key=lambda item: item["created_at"], reverse=True)


def snapshot() -> dict[str, Any]:
    central_exists = CENTRAL_AUDIT_FILE.exists()
    central_events = read_json_list(CENTRAL_AUDIT_FILE)
    pack_files = scan_pack_local_audit_files()
    pack_matches: dict[str, Any] = {}
    for path in pack_files:
        text = safe_read_text(path)
        lines = matching_lines(text, limit=500)
        pack_matches[relative(path)] = {
            "matched_terms": contains_search_term(text),
            "matching_lines": lines,
        }
    return {
        "captured_at": utc_now_iso(),
        "search_terms": SEARCH_TERMS,
        "central_audit": {
            "path": relative(CENTRAL_AUDIT_FILE),
            "exists": central_exists,
            "event_count": len(central_events),
            "metadata": file_metadata(CENTRAL_AUDIT_FILE) if central_exists else None,
            "matching_events": matching_central_events(central_events),
        },
        "pack_local_audits": [file_metadata(path) for path in pack_files],
        "pack_local_matches": pack_matches,
    }


def save_baseline(data: dict[str, Any]) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


def load_baseline() -> dict[str, Any]:
    return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))


def summarize_changes(before: dict[str, Any], after: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    before_central = before.get("central_audit", {})
    after_central = after.get("central_audit", {})
    central_changed = before_central.get("metadata", {}).get("sha256") != after_central.get("metadata", {}).get("sha256")

    before_packs = {item["path"]: item for item in before.get("pack_local_audits", [])}
    after_packs = {item["path"]: item for item in after.get("pack_local_audits", [])}

    changed_pack_paths = []
    for path, after_item in after_packs.items():
        before_item = before_packs.get(path)
        if before_item is None or before_item.get("sha256") != after_item.get("sha256"):
            changed_pack_paths.append(path)

    removed_pack_paths = [path for path in before_packs if path not in after_packs]

    return (
        {
            "changed": central_changed,
            "before_event_count": before_central.get("event_count"),
            "after_event_count": after_central.get("event_count"),
            "before_sha256": before_central.get("metadata", {}).get("sha256"),
            "after_sha256": after_central.get("metadata", {}).get("sha256"),
        },
        {
            "changed": bool(changed_pack_paths or removed_pack_paths),
            "changed_paths": changed_pack_paths,
            "removed_paths": removed_pack_paths,
        },
    )


def new_central_matches(before: dict[str, Any]) -> list[dict[str, Any]]:
    before_hashes = set()
    for event in matching_central_events(read_json_list(CENTRAL_AUDIT_FILE)):
        # placeholder to keep structure uniform if file disappears between steps
        if False:
            before_hashes.add(event["event_hash"])
    before_events = read_json_list(CENTRAL_AUDIT_FILE)
    _ = before_events
    baseline_text = before.get("_computed_before_central_matches", [])
    before_hashes = {item["event_hash"] for item in baseline_text}
    current = matching_central_events(read_json_list(CENTRAL_AUDIT_FILE))
    return [item for item in current if item["event_hash"] not in before_hashes]


def current_pack_matching_lines(paths: list[str]) -> list[dict[str, Any]]:
    rows = []
    for rel_path in paths:
        path = ROOT / rel_path
        if not path.exists():
            continue
        text = safe_read_text(path)
        matched_terms = contains_search_term(text)
        line_hits = matching_lines(text)
        if not matched_terms and not line_hits:
            continue
        rows.append(
            {
                "path": rel_path,
                "matched_terms": matched_terms,
                "line_hits": line_hits,
            }
        )
    return rows


def baseline_command() -> int:
    print("LMCP Audit Write Probe")
    print(f"Repository Root: {ROOT}")
    print(f"Mode: baseline")
    print(f"Central Audit File: {CENTRAL_AUDIT_FILE}")
    backup_path = make_backup(CENTRAL_AUDIT_FILE)
    print(f"Central Audit Backup: {backup_path if backup_path else 'missing; no backup created'}")

    data = snapshot()
    save_baseline(data)

    events = read_json_list(CENTRAL_AUDIT_FILE)
    print(f"Central Audit Event Count: {len(events)}")
    print(f"Pack-Local Audit File Count: {len(data['pack_local_audits'])}")
    print(f"Baseline File: {BASELINE_FILE}")

    print_section("Latest 30 Global Audit Events")
    for event in latest_events(events, limit=30):
        print(compact_event(event))

    print_section("Search Terms")
    for term in SEARCH_TERMS:
        print(f"- {term}")

    print_section("Baseline Summary")
    print(f"- Central sha256: {data['central_audit']['metadata']['sha256'] if data['central_audit']['metadata'] else 'missing'}")
    print(f"- Central modified_at: {data['central_audit']['metadata']['modified_at'] if data['central_audit']['metadata'] else 'missing'}")
    print(f"- Pack-local audit files tracked: {len(data['pack_local_audits'])}")
    print("- Baseline saved successfully.")
    return 0


def compare_command() -> int:
    if not BASELINE_FILE.exists():
        print(f"Baseline file not found: {BASELINE_FILE}", file=sys.stderr)
        print("Run `python3 scripts/audit_write_probe.py --baseline` first.", file=sys.stderr)
        return 1

    print("LMCP Audit Write Probe")
    print(f"Repository Root: {ROOT}")
    print("Mode: compare")
    print(f"Baseline File: {BASELINE_FILE}")

    backup_path = make_backup(CENTRAL_AUDIT_FILE)
    print(f"Central Audit Backup: {backup_path if backup_path else 'missing; no backup created'}")

    before = load_baseline()
    after = snapshot()
    central_change, pack_change = summarize_changes(before, after)

    print_section("Change Summary")
    print(f"- Central audit changed: {'YES' if central_change['changed'] else 'NO'}")
    print(f"- Central event count: {central_change['before_event_count']} -> {central_change['after_event_count']}")
    print(f"- Central sha256 before: {central_change['before_sha256'] or 'missing'}")
    print(f"- Central sha256 after:  {central_change['after_sha256'] or 'missing'}")
    print(f"- Pack-local audit changed: {'YES' if pack_change['changed'] else 'NO'}")
    print(f"- Changed pack-local files: {len(pack_change['changed_paths'])}")
    print(f"- Removed pack-local files: {len(pack_change['removed_paths'])}")

    print_section("New Central Matching Events")
    before_hashes = {
        item["event_hash"] for item in before.get("central_audit", {}).get("matching_events", [])
    }
    current_central_matches = after.get("central_audit", {}).get("matching_events", [])
    new_central_matches = [item for item in current_central_matches if item["event_hash"] not in before_hashes]
    if new_central_matches:
        for row in new_central_matches[:20]:
            print(
                f"- {row['created_at']} | event_type={row['event_type'] or '-'} | title={row['title'] or '-'} "
                f"| rfq={row['buyer_rfq_number'] or '-'} | quote={row['quote_number'] or '-'} "
                f"| matched_terms={', '.join(row['matched_terms']) or '-'}"
            )
    else:
        print("No new central matching events were found relative to baseline.")

    print_section("Changed Pack-Local Audit Files")
    before_pack_matches = before.get("pack_local_matches", {})
    after_pack_matches = after.get("pack_local_matches", {})
    changed_pack_rows = []
    for rel_path in pack_change["changed_paths"]:
        current = after_pack_matches.get(rel_path, {})
        previous = before_pack_matches.get(rel_path, {})
        previous_lines = set(previous.get("matching_lines", []))
        new_lines = [line for line in current.get("matching_lines", []) if line not in previous_lines]
        if not current.get("matched_terms") and not new_lines:
            continue
        changed_pack_rows.append(
            {
                "path": rel_path,
                "matched_terms": current.get("matched_terms", []),
                "line_hits": new_lines or current.get("matching_lines", [])[:10],
            }
        )
    if not changed_pack_rows:
        print("No changed pack-local audit files with matching search terms were found.")
    else:
        for row in changed_pack_rows[:20]:
            print(f"- {row['path']} | matched_terms={', '.join(row['matched_terms']) or '-'}")
            for hit in row["line_hits"][:10]:
                print(f"  {hit}")

    print_section("Verdict")
    central_pass = bool(new_central_matches)
    pack_partial = bool(changed_pack_rows)
    if central_pass:
        print("PASS: central audit captured the supervised UI action")
    elif pack_partial:
        print("PARTIAL: pack-local audit captured the action but central audit did not")
    else:
        print("FAIL: no audit file captured the action")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Baseline/compare audit write probe for supervised UI actions.")
    parser.add_argument("--baseline", action="store_true", help="Capture a baseline of current central and pack-local audit state.")
    parser.add_argument("--compare", action="store_true", help="Compare current audit state against the saved baseline.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.baseline and args.compare:
        print("Use either --baseline or --compare, not both.", file=sys.stderr)
        return 1
    if args.baseline:
        return baseline_command()
    if args.compare:
        return compare_command()
    print("Use one of: --baseline, --compare", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
