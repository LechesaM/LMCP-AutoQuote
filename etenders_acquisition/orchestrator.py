import time
import json
import os

from config import *
from registry import SourceRegistry
from fetcher import Fetcher
from event_bus import EventBus
from boq_worker import BOQWorker


class Orchestrator:

    def __init__(self):
        self.registry = SourceRegistry()
        self.fetcher = Fetcher()
        self.bus = EventBus()

        self.state = self.load_state()

        for i in range(BOQ_WORKERS):
            BOQWorker(self.bus, i).start()

    def load_state(self):
        if not os.path.exists(CHECKPOINT_FILE):
            return {"start": 0}
        return json.load(open(CHECKPOINT_FILE))

    def save_state(self):
        json.dump(self.state, open(CHECKPOINT_FILE, "w"))

    def run(self):

        empty = 0

        while True:

            start = self.state["start"]
            print(f"FETCH start={start}")

            items = self.fetcher.fetch(start)

            if items is None:
                print("fetch failed")
                time.sleep(5)
                continue

            if len(items) == 0:
                empty += 1
                if empty >= 3:
                    print("END OF DATASET")
                    break

                self.state["start"] += PAGE_SIZE
                self.save_state()
                continue

            empty = 0

            changed_batch = []

            for item in items:
                t = self.registry.normalize(item)

                if self.registry.is_changed(t):
                    changed_batch.append(t)
                    self.bus.publish(t)

            if changed_batch:
                self.registry.upsert_batch(changed_batch)

            self.state["start"] += PAGE_SIZE
            self.save_state()

            time.sleep(0.5)
