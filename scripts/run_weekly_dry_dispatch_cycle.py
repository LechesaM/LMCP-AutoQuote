from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.testing.dry_dispatch_evidence import (
    append_dry_dispatch_cycle,
    build_dry_dispatch_cycle,
    evaluate_live_submission_gate,
    list_fixture_paths,
    load_fixture_manifest,
    read_dry_dispatch_cycles,
    read_fixture_manifest,
    resolve_tier_manifest_path,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a weekly dry-dispatch evidence cycle without changing workflow tracks.")
    parser.add_argument("--tier-label", required=True, help="Tier label such as tier_10 or tier_25.")
    parser.add_argument("--fixtures-dir", help="Directory of RFQ JSON fixtures.")
    parser.add_argument("--manifest", help="JSON manifest listing fixture paths.")
    parser.add_argument("--manifests-dir", default="tests/fixtures/manifests", help="Directory containing tier manifest files for auto-resolution.")
    parser.add_argument("--week-ending", help="Week-ending date in YYYY-MM-DD format.")
    parser.add_argument("--cycle-label", default="weekly_dry_dispatch", help="Cycle label to record in the evidence registry.")
    parser.add_argument("--print-gate", action="store_true", help="Print the live submission gate evaluation after recording the cycle.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.fixtures_dir and args.manifest:
        raise SystemExit("Specify at most one of --fixtures-dir or --manifest.")

    manifest_metadata = {}
    if args.manifest:
        manifest_path = Path(args.manifest)
        manifest_metadata = read_fixture_manifest(manifest_path)
        fixtures = load_fixture_manifest(manifest_path)
    elif args.fixtures_dir:
        fixtures = list_fixture_paths(args.fixtures_dir)
    else:
        manifest_path = resolve_tier_manifest_path(args.tier_label, args.manifests_dir)
        if not manifest_path.exists():
            raise SystemExit(f"No tier manifest found for {args.tier_label}: {manifest_path}")
        manifest_metadata = read_fixture_manifest(manifest_path)
        fixtures = load_fixture_manifest(manifest_path)

    cycle = build_dry_dispatch_cycle(
        fixtures,
        tier_label=args.tier_label,
        week_ending=args.week_ending,
        cycle_label=args.cycle_label,
        manifest_metadata=manifest_metadata,
    )
    stored_cycle = append_dry_dispatch_cycle(cycle)
    print(json.dumps(stored_cycle, ensure_ascii=False, indent=2, sort_keys=True))
    if args.print_gate:
        gate = evaluate_live_submission_gate(read_dry_dispatch_cycles())
        print(json.dumps(gate, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
