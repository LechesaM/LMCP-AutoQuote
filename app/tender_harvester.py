from datetime import datetime
from typing import List, Dict
import requests
from bs4 import BeautifulSoup


ETENDERS_URL = "https://www.etenders.gov.za/Home/opportunities"


def harvest_etenders() -> List[Dict]:
    tenders: List[Dict] = []

    try:
        response = requests.get(
            ETENDERS_URL,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Safari/605.1.15"
            },
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("table tbody tr")

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue

            title = cols[0].get_text(" ", strip=True)
            department = cols[1].get_text(" ", strip=True) if len(cols) > 1 else ""
            closing_date = cols[2].get_text(" ", strip=True) if len(cols) > 2 else ""

            link = ""
            anchor = cols[0].find("a")
            if anchor and anchor.get("href"):
                href = anchor.get("href")
                if href.startswith("http"):
                    link = href
                else:
                    link = f"https://www.etenders.gov.za{href}"

            tenders.append(
                {
                    "title": title,
                    "department": department,
                    "closing_date": closing_date,
                    "link": link,
                    "source": "eTenders",
                    "date_harvested": datetime.utcnow().isoformat(),
                }
            )

        return tenders

    except Exception as e:
        return [
            {
                "title": "Harvester Error",
                "department": "",
                "closing_date": "",
                "link": "",
                "source": "eTenders",
                "date_harvested": datetime.utcnow().isoformat(),
                "error": str(e),
            }
        ]
