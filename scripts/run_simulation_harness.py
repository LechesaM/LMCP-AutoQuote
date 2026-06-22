from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation_harness_service import run_simulation_harness


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Sprint 5 governed RFQ simulation harness.")
    parser.add_argument("--max-rfqs", type=int, default=100, help="Number of RFQs to process. Default: 100.")
    parser.add_argument("--fixture", action="append", default=None, help="Optional fixture JSON path. Repeat to override the default corpus.")
    parser.add_argument(
        "--inject-approval-for",
        action="append",
        default=None,
        help="Optional base tender id or generated RFQ id to mark as human-approved in the simulation.",
    )
    parser.add_argument("--run-label", default="sprint5", help="Optional label prefix for the simulation run directory.")
    args = parser.parse_args(argv)

    result = run_simulation_harness(
        max_rfqs=args.max_rfqs,
        fixture_paths=args.fixture,
        inject_approvals_for=args.inject_approval_for,
        run_label=args.run_label,
    )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
