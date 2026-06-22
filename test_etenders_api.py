import requests

url = "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities"

params = {
    "draw": 1,
    "start": 0,
    "length": 10,
    "status": 1
}

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.etenders.gov.za/Home/opportunities"
}

r = requests.get(url, params=params, headers=headers)

print("STATUS:", r.status_code)
print("RAW TEXT SAMPLE:\n")
print(r.text[:1000])
