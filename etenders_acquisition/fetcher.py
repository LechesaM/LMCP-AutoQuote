import requests
from config import URL, PAGE_SIZE, TIMEOUT

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

class Fetcher:

    def fetch(self, start: int):
        try:
            r = requests.get(
                URL,
                params={"start": start, "length": PAGE_SIZE},
                headers=HEADERS,
                timeout=TIMEOUT
            )

            if r.status_code != 200:
                return None

            return r.json().get("data", []) or []

        except:
            return None
