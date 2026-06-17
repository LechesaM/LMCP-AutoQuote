from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.runtime_paths import get_runtime_paths
from app.services.acquisition_backed_validation_service import DEFAULT_LIMIT, build_acquisition_backed_validation_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the acquisition-backed 10-RFQ supervised validation.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Maximum RFQs to include in the validation report.")
    parser.add_argument(
        "--output",
        type=str,
        default=str(get_runtime_paths().manual_production_dir / "acquisition_backed_validation_report_10.json"),
        help="Path to the auditable JSON report.",
    )
    parser.add_argument(
        "--live-rfq-store",
        type=str,
        default=str(get_runtime_paths().runtime_root / "live_rfqs.json"),
        help="Path to the live RFQ store JSON.",
    )
    parser.add_argument(
        "--pilot-runs",
        type=str,
        default=str(get_runtime_paths().manual_production_dir / "pilot_runs.jsonl"),
        help="Path to the supervised production traces JSONL file.",
    )
    parser.add_argument("--emit-progress", action="store_true", help="Emit progress events as JSON lines on stderr.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = build_acquisition_backed_validation_report(
        limit=args.limit,
        live_rfqs_path=args.live_rfq_store,
        pilot_runs_path=args.pilot_runs,
        output_path=args.output,
        emit_progress=args.emit_progress,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
