from datetime import datetime
import traceback
import time
import requests

API_BASE = "http://localhost:8000"

RETRY_LIMIT = 2
SLEEP_SECONDS = 1800  # 30 minutes


def log(msg):
    print(f"[SELF-HEAL] {datetime.utcnow().isoformat()} | {msg}")


def run_cycle():
    try:
        log("Running final automation cycle")

        r = requests.post(f"{API_BASE}/final-automation/run-once", timeout=900)
        data = r.json()

        if data.get("status") != "ok":
            log(f"Cycle returned non-ok: {data}")

        return True

    except Exception as e:
        log(f"Cycle failed: {e}")
        log(traceback.format_exc())
        return False


def run_with_retry():
    for attempt in range(RETRY_LIMIT):
        success = run_cycle()

        if success:
            return True

        log(f"Retry attempt {attempt+1}/{RETRY_LIMIT}")
        time.sleep(5)

    log("All retries failed — skipping cycle")
    return False


def loop():
    log("Starting autonomous self-healing loop")

    while True:
        try:
            run_with_retry()
        except Exception as e:
            log(f"Critical loop error: {e}")
            log(traceback.format_exc())

        log(f"Sleeping {SLEEP_SECONDS} seconds")
        time.sleep(SLEEP_SECONDS)
