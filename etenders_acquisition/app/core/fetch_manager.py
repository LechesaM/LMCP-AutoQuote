import requests
import time
from app.config.settings import FETCH_TIMEOUT, MAX_RETRIES, BACKOFF_FACTOR

class FetchManager:

    def fetch(self, url):
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                r = requests.get(
                    url,
                    timeout=FETCH_TIMEOUT,
                    headers={"User-Agent": "Mozilla/5.0"}
                )

                if r.status_code == 200:
                    return r.text

                last_error = f"HTTP {r.status_code}"

            except Exception as e:
                last_error = str(e)

            time.sleep(BACKOFF_FACTOR ** attempt)

        raise Exception(f"Fetch failed: {last_error}")
