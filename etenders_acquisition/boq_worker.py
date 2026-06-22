import threading
import time

class BOQWorker(threading.Thread):

    def __init__(self, bus, worker_id=0):
        super().__init__(daemon=True)
        self.bus = bus
        self.worker_id = worker_id

    def run(self):
        while True:
            tender = self.bus.consume()
            self.process(tender)

    def process(self, tender):
        print(f"[BOQ-{self.worker_id}] {tender.id} - {tender.title}")

        # future pipeline stages:
        # 1. document download
        # 2. pdf parsing
        # 3. BOQ extraction
        # 4. classification
        # 5. indexing

        time.sleep(0.2)
