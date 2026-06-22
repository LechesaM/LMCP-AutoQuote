import time
import json
import random
import logging
import os
import hashlib
import requests
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

from kafka import KafkaProducer

# =========================
# CONFIG
# =========================

URL = "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}

PAGE_SIZE = 10
MAX_RETRIES = 5
TIMEOUT = 30

CHECKPOINT_FILE = "checkpoint.json"

KAFKA_BOOTSTRAP = "localhost:9092"
RAW_TOPIC = "etenders.raw"

# =========================
# LOGGING
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("fetch_manager")


# =========================
# STATE
# =========================

@dataclass
class FetchState:
    start: int = 0
    total_processed: int = 0
    failures: int = 0
    circuit_open_until: float = 0.0


# =========================
# CHECKPOINT
# =========================

class CheckpointManager:

    @staticmethod
    def load():
        if not os.path.exists(CHECKPOINT_FILE):
            return FetchState()

        try:
            with open(CHECKPOINT_FILE, "r") as f:
                return FetchState(**json.load(f))
        except Exception:
            log.warning("Checkpoint corrupted, resetting.")
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
        self.open_until = 0

    def record_failure(self):
        self.failures += 1
        if self.failures >= self.threshold:
            self.open_until = time.time() + self.cooldown
            log.warning("CIRCUIT OPENED")

    def record_success(self):
        self.failures = 0

    def allow(self):
        return time.time() > self.open_until


# =========================
# UTILS
# =========================

def adaptive_sleep(base=1.0):
    time.sleep(base + random.uniform(0.2, 1.5))


def make_dedup_key(item: Dict[str, Any]) -> str:
    raw = json.dumps(item, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


def normalize(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standard enterprise schema layer
    """
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "department": item.get("department"),
        "published": item.get("publishedDate"),
        "closing": item.get("closingDate"),
        "url": item.get("url"),
        "raw": item,
    }


def should_trigger_boq(item: Dict[str, Any]) -> bool:
    title = (item.get("title") or "").lower()
    keywords = ["construction", "building", "maintenance", "renovation", "supply"]
    return any(k in title for k in keywords)


# =========================
# FETCH MANAGER
# =========================

class FetchManager:

    def __init__(self):
        self.state = CheckpointManager.load()
        self.circuit = CircuitBreaker()

        self.kafka = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode("utf-8")
        )

        self.seen = set()  # in-memory dedupe (upgrade later to Redis)

    def build_params(self, start):
        return {
            "draw": 1,
            "start": start,
            "length": PAGE_SIZE,
            "status": 1
        }

    def fetch_page(self, start):
        retries = 0

        while retries < MAX_RETRIES:

            if not self.circuit.allow():
                wait = max(self.state.circuit_open_until - time.time(), 1)
                log.warning(f"Circuit open. Sleeping {wait:.1f}s")
                time.sleep(wait)
                continue

            try:
                resp = requests.get(
                    URL,
                    params=self.build_params(start),
                    headers=HEADERS,
                    timeout=TIMEOUT
                )

                if resp.status_code != 200:
                    raise Exception(f"HTTP {resp.status_code}")

                data = resp.json()
                items = data.get("data", []) or []

                return items

            except Exception as e:
                retries += 1
                self.circuit.record_failure()

                wait = min(2 ** retries, 30)
                log.warning(f"Retry {retries} failed start={start}: {e}")
                time.sleep(wait)

        return None

    def publish(self, item: Dict[str, Any]):
        key = make_dedup_key(item)

        if key in self.seen:
            return

        self.seen.add(key)

        event = {
            "dedup_key": key,
            "source": "etenders",
            "normalized": normalize(item),
            "boq_trigger": should_trigger_boq(item),
            "ingested_at": time.time()
        }

        self.kafka.send(RAW_TOPIC, value=event)

    def run(self):
        log.info("Fetch Manager started (Kafka mode)")

        empty_streak = 0

        while True:

            start = self.state.start
            log.info(f"Fetching start={start}")

            items = self.fetch_page(start)

            if items is None:
                log.error("Hard failure. stopping.")
                break

            if len(items) == 0:
                empty_streak += 1
                log.info(f"Empty page {empty_streak}/3")

                if empty_streak >= 3:
                    log.info("End of dataset detected.")
                    break

                self.state.start += PAGE_SIZE
                CheckpointManager.save(self.state)
                adaptive_sleep(1)
                continue

            empty_streak = 0

            log.info(f"Page returned {len(items)} items")

            for item in items:
                self.publish(item)

            self.state.total_processed += len(items)
            self.state.start += PAGE_SIZE

            CheckpointManager.save(self.state)
            self.circuit.record_success()

            adaptive_sleep(0.8)

        log.info(f"DONE. Total processed={self.state.total_processed}")


# =========================
# ENTRY
# =========================

if __name__ == "__main__":
    FetchManager().run()
