#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = (
    RUNTIME_DIR
    / "supplier_expansion"
    / "manufacturer_part_index.json"
)

OUT_DIR = RUNTIME_DIR / "supplier_expansion"

OUTPUT_FILE = OUT_DIR / "filtered_manufacturer_part_index_v2.json"
SUMMARY_FILE = OUT_DIR / "part_quality_filter_v2_summary.json"


UNIT_RANGE_PATTERN = re.compile(
    r"^\d+(\.\d+)?[-X]\d+(\.\d+)?(MM|CM|M|IN|V|VOLT|W|WATT|KW|AMP|AH|CC|L|KG)$",
    re.I,
)

UNIT_SINGLE_PATTERN = re.compile(
    r"^\d+(\.\d+)?(MM|CM|M|IN|V|VOLT|W|WATT|KW|AMP|AH|CC|L|KG|MW)$",
    re.I,
)

DIMENSION_WITH_X_PATTERN = re.compile(
    r"^\d+(\.\d+)?(MM|CM|M|IN)?X\d+(\.\d+)?(MM|CM|M|IN)?(X\d+(\.\d+)?(MM|CM|M|IN)?)?$",
    re.I,
)

SPEC_WORDS = {
    "NON-FERROUS",
    "SUB-STRUCTURES",
    "PRE-TENSIONING",
    "V-SHAPED",
    "SELF-CENTERING",
    "QUAD-CORE",
    "LITHIUM-ION",
    "TYPE-A",
    "TYPE-C",
    "WI-FI",
    "4-JAW",
    "3-SIDED",
    "1-INCH",
    "ISO40",
    "TO1000MM",
    "HIGHX100MMX50MM",
}

TRUE_PART_HINT_PATTERN = re.compile(
    r"^(NU|NJ|NUP|N|HK|HE|AHX?|TSNA|QR|SS|LF|SPC|UCM|FAG|SKF|NSK|TIMKEN|E|Z|RMS|NC|D|M|F|XLJ|ALS|RLS|QJM|MJ)[A-Z0-9\-\/]+$",
    re.I,
)

BEARING_LIKE_PATTERN = re.compile(
    r"^([0-9]{3,5}[A-Z]{0,4}([\-\/][A-Z0-9]+)*|[A-Z]{1,4}[0-9]{2,6}[A-Z0-9\-\/]*)$",
    re.I,
)

SUPPLIER_CODE_PATTERN = re.compile(
    r"^[0-9]{3,6}-[0-9]{2,6}(-[0-9]{1,6})?$",
    re.I,
)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_json(path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def classify(part):
    p = str(part or "").strip().upper()

    if not p:
        return "noise"

    if p in SPEC_WORDS:
        return "technical_spec"

    if UNIT_RANGE_PATTERN.match(p):
        return "technical_spec"

    if UNIT_SINGLE_PATTERN.match(p):
        return "technical_spec"

    if DIMENSION_WITH_X_PATTERN.match(p):
        return "technical_spec"

    if re.match(r"^\d+-\d+(MM|CM|M|IN|V|W|AH|CC)$", p):
        return "technical_spec"

    if re.match(r"^\d+/\d+$", p):
        return "numeric_code_review"

    if p.isdigit():
        return "numeric_code_review"

    if TRUE_PART_HINT_PATTERN.match(p):
        return "true_part_number"

    if SUPPLIER_CODE_PATTERN.match(p):
        return "true_part_number"

    if BEARING_LIKE_PATTERN.match(p):
        # Reject obvious specs that slipped through
        if any(unit in p for unit in ["MM", "CM", "VOLT", "WATT", "AMP", "AH", "CC"]):
            return "technical_spec"

        return "true_part_number"

    if re.search(r"[A-Z]", p) and re.search(r"\d", p) and len(p) >= 5:
        if any(unit in p for unit in ["MM", "CM", "VOLT", "WATT", "AMP", "AH", "CC"]):
            return "technical_spec"

        return "numeric_code_review"

    return "noise"


def main():
    data = load_json(INPUT_FILE, default={})
    part_index = data.get("manufacturer_part_index", {})

    buckets = defaultdict(dict)

    for part, records in part_index.items():
        cls = classify(part)
        buckets[cls][part] = records

    output = {
        "generated_at": now_iso(),
        "true_part_numbers": buckets.get("true_part_number", {}),
        "numeric_code_review": buckets.get("numeric_code_review", {}),
        "technical_specs": buckets.get("technical_spec", {}),
        "noise": buckets.get("noise", {}),
    }

    summary = {
        "generated_at": output["generated_at"],
        "input_parts": len(part_index),
        "true_part_numbers": len(output["true_part_numbers"]),
        "numeric_code_review": len(output["numeric_code_review"]),
        "technical_specs": len(output["technical_specs"]),
        "noise": len(output["noise"]),
        "classification_counts": {
            k: len(v) for k, v in buckets.items()
        },
    }

    write_json(OUTPUT_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"Filtered V2 part index written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Input parts: {summary['input_parts']}")
    print(f"True part numbers: {summary['true_part_numbers']}")
    print(f"Numeric review: {summary['numeric_code_review']}")
    print(f"Technical specs: {summary['technical_specs']}")
    print(f"Noise: {summary['noise']}")


if __name__ == "__main__":
    main()
