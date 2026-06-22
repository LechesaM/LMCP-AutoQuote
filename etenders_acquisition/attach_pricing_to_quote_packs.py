import json
import shutil
from pathlib import Path


RUNTIME_DIR = Path("/Users/cash/Documents/runtime/manual_production")
QUOTE_PACK_DIR = RUNTIME_DIR / "quote_packs"
PRICING_SUMMARY_DIR = Path("/Users/cash/Documents/runtime/pricing_summaries")
WORKFLOW_STATE_FILE = RUNTIME_DIR / "workflow_state.jsonl"


def read_jsonl(path):
    rows = []

    if not path.exists():
        return rows

    with open(path, "r") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            try:
                rows.append(json.loads(line))
            except Exception:
                continue

    return rows


def latest_workflows(rows):
    latest = {}

    for row in rows:
        workflow_id = row.get("workflow_id")

        if not workflow_id:
            continue

        latest[workflow_id] = row

    return list(latest.values())


def safe_name(value):
    value = str(value or "unknown")
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in value)[:80]


def summary_file_for_tender(tender_id):
    filename = tender_id.replace("/", "_") + ".json"
    return PRICING_SUMMARY_DIR / filename


def main():
    rows = read_jsonl(WORKFLOW_STATE_FILE)
    workflows = latest_workflows(rows)

    attached = 0
    missing_summary = 0
    missing_pack = 0

    for wf in workflows:
        if wf.get("quote_ready") is not True:
            continue

        tender_id = wf.get("tender_id")
        if not tender_id:
            continue

        summary_path = summary_file_for_tender(tender_id)

        if not summary_path.exists():
            missing_summary += 1
            continue

        pack_info = wf.get("quote_pack") or {}
        pack_dir = pack_info.get("pack_dir")

        if pack_dir:
            target_dir = Path(pack_dir)
        else:
            target_dir = QUOTE_PACK_DIR / safe_name(tender_id)

        if not target_dir.exists():
            missing_pack += 1
            continue

        target_path = target_dir / "pricing_summary.json"

        shutil.copyfile(summary_path, target_path)

        quote_summary_path = target_dir / "quote_summary.json"

        if quote_summary_path.exists():
            try:
                with open(quote_summary_path, "r") as f:
                    quote_summary = json.load(f)

                with open(summary_path, "r") as f:
                    pricing_summary = json.load(f)

                quote_summary["pricing_summary"] = pricing_summary
                quote_summary["pricing_summary_path"] = str(target_path)
                quote_summary["pricing_status"] = pricing_summary.get("status")

                with open(quote_summary_path, "w") as f:
                    json.dump(quote_summary, f, indent=2, ensure_ascii=False)

            except Exception:
                pass

        attached += 1

    print(
        "Pricing attach complete | "
        f"attached={attached} "
        f"missing_summary={missing_summary} "
        f"missing_pack={missing_pack}"
    )


if __name__ == "__main__":
    main()
