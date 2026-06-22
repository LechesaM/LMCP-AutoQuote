import hashlib

class DuplicateDetector:

    def make_hash(self, tender):
        raw = f"{tender.get('title')}|{tender.get('reference')}|{tender.get('closing_date')}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def exists(self, db, h):
        cur = db.cursor()
        cur.execute("SELECT 1 FROM tenders WHERE hash=?", (h,))
        return cur.fetchone() is not None
