import time
import json
import random
import logging
import os
import requests
import hashlib
from dataclasses import dataclass, asdict

from storage_postgres import PostgreSQLStore


# =========================
# CONFIG
# =========================

URL = "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )
}

PAGE_SIZE = 10
MAX_RETRIES = 5
TIMEOUT = 30

CHECKPOINT_FILE = "checkpoint.json"


# =========================
# LOGGING
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("fetch_manager")


# =========================
# STATE MODEL
# =========================

@dataclass
class FetchState:
    start: int = 0
    total_processed: int = 0
    failures: int = 0
    circuit_open_until: float = 0.0


@dataclass
class TenderRecord:
    tender_id: str
    title: str
    department: str
    province: str
    closing_date: str
    raw: dict

    def dedup_key(self) -> str:
        base = "|".join([
            self.tender_id or "",
            self.title or "",
            self.department or "",
            self.closing_date or "",
        ])

        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def content_hash(self) -> str:
        payload = json.dumps(
            self.raw,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )

        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# =========================
# SAFE CHECKPOINT
# =========================

class CheckpointManager:

    @staticmethod
    def load() -> FetchState:
        if not os.path.exists(CHECKPOINT_FILE):
            return FetchState()

        try:
            with open(CHECKPOINT_FILE, "r") as f:
                data = json.load(f)

            return FetchState(**data)

        except Exception:
            log.warning("Checkpoint corrupted. Starting fresh.")
            return FetchState()

    @staticmethod
    def save(state: FetchState):
        tmp = CHECKPOINT_FILE + ".tmp"

        with open(tmp, "w") as f:
            json.dump(asdict(state), f)

        os.replace(tmp, CHECKPOINT_FILE)


# =========================
# CIRCUIT BREAKER
# =========================

class CircuitBreaker:

    def __init__(self, threshold=5, cooldown=60):
        self.threshold = threshold
        self.cooldown = cooldown
        self.failures = 0
        self.open_until = 0.0

    def record_failure(self):
        self.failures += 1

        if self.failures >= self.threshold:
            self.open_until = time.time() + self.cooldown
            log.warning(f"CIRCUIT OPEN for {self.cooldown}s")

    def record_success(self):
        self.failures = 0
        self.open_until = 0.0

    def allow(self) -> bool:
        return time.time() > self.open_until


# =========================
# ADAPTIVE SLEEP
# =========================

def adaptive_sleep(base=1.0):
    jitter = random.uniform(0.2, 1.5)
    time.sleep(base + jitter)


# =========================
# FETCH MANAGER
# =========================

class FetchManager:

    def __init__(self):
        self.state = CheckpointManager.load()
        self.circuit = CircuitBreaker()
        self.store = PostgreSQLStore()

    def build_params(self, start: int) -> dict:
        return {
            "draw": 1,
            "start": start,
            "length": PAGE_SIZE,
            "status": 1,
        }

    def fetch_page(self, start: int):
        retries = 0

        while retries < MAX_RETRIES:

            if not self.circuit.allow():
                wait = max(self.circuit.open_until - time.time(), 1)
                log.warning(f"Circuit open. Sleeping {wait:.1f}s")
                time.sleep(wait)
                continue

            try:
                resp = requests.get(
                    URL,
                    params=self.build_params(start),
                    headers=HEADERS,
                    timeout=TIMEOUT,
                )

                if resp.status_code != 200:
                    raise Exception(f"HTTP {resp.status_code}")

                data = resp.json()
                items = data.get("data", [])

                if items is None:
                    items = []

                return items

            except Exception as e:
                retries += 1
                self.circuit.record_failure()

                wait = min(2 ** retries, 30)

                log.warning(
                    f"Fetch failed start={start} "
                    f"attempt={retries}/{MAX_RETRIES} "
                    f"retrying in {wait}s | error={e}"
                )

                time.sleep(wait)

        return None

    def normalize_item(self, item: dict) -> TenderRecord:
        tender_id = (
            item.get("tender_No")
            or item.get("tenderNo")
            or item.get("tender_number")
            or item.get("id")
            or ""
        )

        title = (
            item.get("description")
            or item.get("title")
            or item.get("tenderDescription")
            or ""
        )

        department = (
            item.get("department")
            or item.get("organ_of_State")
            or item.get("organOfState")
            or item.get("buyer")
            or ""
        )

        province = item.get("province") or ""

        closing_date = (
            item.get("closing_Date")
            or item.get("closingDate")
            or item.get("closing_date")
            or ""
        )

        return TenderRecord(
            tender_id=str(tender_id),
            title=str(title),
            department=str(department),
            province=str(province),
            closing_date=str(closing_date),
            raw=item,
        )

    def run(self):
        log.info("Fetch Manager started...")

        empty_streak = 0

        while True:
            start = self.state.start

            log.info(f"Fetching start={start}")

            items = self.fetch_page(start)

            if items is None:
                log.error("Page failed after retries. Stopping safely.")
                break

            if len(items) == 0:
                empty_streak += 1
                log.info(f"Empty page {empty_streak}/3")

                if empty_streak >= 3:
                    log.info("No more data confirmed. Stopping safely.")
                    break

                self.state.start += PAGE_SIZE
                CheckpointManager.save(self.state)
                adaptive_sleep(1)
                continue

            empty_streak = 0

            log.info(f"Page returned {len(items)} items")

            records = [self.normalize_item(item) for item in items]

            inserted, updated, skipped = self.store.upsert_batch(records)

            log.info(
                f"DB write complete | "
                f"inserted={inserted} updated={updated} skipped={skipped}"
            )

            self.state.total_processed += len(items)
            self.state.start += PAGE_SIZE

            CheckpointManager.save(self.state)

            self.circuit.record_success()

            adaptive_sleep(0.8)

        self.store.close()

        log.info(f"DONE. Total processed: {self.state.total_processed}")


# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    FetchManager().run()
