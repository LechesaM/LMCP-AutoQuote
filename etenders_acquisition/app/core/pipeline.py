from app.core.fetch_manager import FetchManager
from app.core.duplicate_detector import DuplicateDetector
from app.db.sqlite import get_db
from app.config.sources import SOURCES

class Pipeline:

    def __init__(self):
        self.fetcher = FetchManager()
        self.dup = DuplicateDetector()
        self.db = get_db()

    def run(self):
        for source in SOURCES:
            if not source["enabled"]:
                continue

            print(f"Fetching: {source['name']}")

            html = self.fetcher.fetch(source["url"])

            tenders = self.parse(html)

            for t in tenders:
                h = self.dup.make_hash(t)

                if self.dup.exists(self.db, h):
                    continue

                self.save(t, h, source["name"])

    def parse(self, html):
        # TEMP placeholder (we fix in Milestone 2)
        return []

    def save(self, tender, h, source):
        cur = self.db.cursor()
        cur.execute("""
            INSERT INTO tenders (hash, title, reference, closing_date, source, raw)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            h,
            tender.get("title"),
            tender.get("reference"),
            tender.get("closing_date"),
            source,
            str(tender)
        ))
        self.db.commit()
