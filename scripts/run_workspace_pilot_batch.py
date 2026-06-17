from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_workspace_pilot import main as run_workspace_pilot_main


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _default_pilots() -> List[str]:
    return ["PILOT-001", "PILOT-002", "PILOT-003"]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run all pilot workspace folders in sequence.")
    parser.add_argument("--workspace-root", required=True, help="Pilot workspace root containing PILOT-001 etc.")
    parser.add_argument(
        "--pilot-id",
        action="append",
        default=None,
        help="Pilot folder name such as PILOT-001. Repeat to override the default batch order.",
    )
    parser.add_argument("--pricing-file", default=None, help="Optional pricing JSON file to pass to each dry-run.")
    parser.add_argument("--instructions-text-file", default=None, help="Optional text file to use as tender instructions.")
    args = parser.parse_args(argv)

    pilot_ids = args.pilot_id or _default_pilots()
    results: List[Dict[str, Any]] = []
    overall_exit_code = 0

    for pilot_id in pilot_ids:
        exit_code = run_workspace_pilot_main(
            [
                "--workspace-root",
                args.workspace_root,
                "--pilot-id",
                pilot_id,
                *(
                    ["--pricing-file", args.pricing_file]
                    if _clean(args.pricing_file)
                    else []
                ),
                *(
                    ["--instructions-text-file", args.instructions_text_file]
                    if _clean(args.instructions_text_file)
                    else []
                ),
            ]
        )
        results.append({"pilot_id": pilot_id, "exit_code": exit_code})
        if exit_code != 0:
            overall_exit_code = exit_code

    print(
        json.dumps(
            {
                "workspace_root": args.workspace_root,
                "pilot_ids": pilot_ids,
                "results": results,
                "overall_exit_code": overall_exit_code,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return overall_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
