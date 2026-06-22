import subprocess
import sys
import time
import json
from pathlib import Path


RUNTIME_METRICS = Path(
    "/Users/cash/Documents/runtime/manual_production/safe_runtime_metrics.jsonl"
)

MAX_CYCLES = 20


def run(cmd):
    print(f"\n=== Running: {' '.join(cmd)} ===")
    result = subprocess.run(cmd, text=True)

    if result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        sys.exit(result.returncode)


def latest_metrics():
    if not RUNTIME_METRICS.exists():
        return {}

    last = None

    with open(RUNTIME_METRICS, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                last = line

    if not last:
        return {}

    try:
        return json.loads(last)
    except Exception:
        return {}


def queue_counts():
    metrics = latest_metrics()
    payload = metrics.get("payload", {})
    workflow = payload.get("workflow_summary", {})
    queue = workflow.get("queue_summary", {})

    return {
        "queued": int(queue.get("queued_jobs", 0) or 0),
        "pending": int(queue.get("running_jobs", 0) or 0),
        "completed": int(queue.get("completed_jobs", 0) or 0),
        "blocked": int(queue.get("blocked_jobs", 0) or 0),
        "failed": int(queue.get("failed_jobs", 0) or 0),
        "total": int(queue.get("total_jobs", 0) or 0),
    }


def main():
    print("Starting quote pipeline automation...")

    run(["python3", "refresh_runtime_metrics.py"])

    for cycle in range(1, MAX_CYCLES + 1):
        counts = queue_counts()

        print(
            f"\nCycle {cycle} status | "
            f"queued={counts['queued']} "
            f"pending={counts['pending']} "
            f"completed={counts['completed']} "
            f"blocked={counts['blocked']} "
            f"failed={counts['failed']} "
            f"total={counts['total']}"
        )

        if counts["queued"] == 0 and counts["pending"] == 0:
            print("\nPipeline complete. No queued or pending quote-pack items remain.")
            break

        if counts["queued"] > 0:
            run(["python3", "quote_worker.py"])

        run(["python3", "quote_pack_generator.py"])
        run(["python3", "refresh_runtime_metrics.py"])

        time.sleep(0.5)

    final = queue_counts()

    print(
        "\nFINAL STATUS | "
        f"queued={final['queued']} "
        f"pending={final['pending']} "
        f"completed={final['completed']} "
        f"blocked={final['blocked']} "
        f"failed={final['failed']} "
        f"total={final['total']}"
    )


if __name__ == "__main__":
    main()
