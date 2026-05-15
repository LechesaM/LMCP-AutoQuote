#!/usr/bin/env python3
"""
Run Clean Ink Extraction V3 from terminal.

Examples:
    python3 scripts/test_clean_ink_v3.py runtime/handwriting_simulation/my_sample.png
    python3 scripts/test_clean_ink_v3.py runtime/handwriting_simulation/my_sample.png --sensitivity 45 --job-id TEST-INK-001
"""

import argparse
import json

from app.services.clean_ink_extraction_v3 import extract_clean_ink_v3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path", help="Path to handwriting sample image")
    parser.add_argument("--job-id", default=None)
    parser.add_argument("--sensitivity", type=int, default=38)
    parser.add_argument("--crop-padding", type=int, default=14)
    args = parser.parse_args()

    result = extract_clean_ink_v3(
        args.input_path,
        job_id=args.job_id,
        sensitivity=args.sensitivity,
        crop_padding=args.crop_padding,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
