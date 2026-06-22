#!/usr/bin/env python3
import requests
import json

URL = "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities"

params = {
    "draw": "1",
    "columns[0][data]": "department",
    "columns[0][name]": "",
    "columns[0][searchable]": "true",
    "columns[0][orderable]": "true",
    "columns[0][search][value]": "",
    "columns[0][search][regex]": "false",
    "columns[1][data]": "description",
    "columns[1][name]": "",
    "columns[1][searchable]": "true",
    "columns[1][orderable]": "true",
    "columns[1][search][value]": "",
    "columns[1][search][regex]": "false",
    "columns[2][data]": "closingDate",
    "columns[2][name]": "",
    "columns[2][searchable]": "true",
    "columns[2][orderable]": "true",
    "columns[2][search][value]": "",
    "columns[2][search][regex]": "false",
    "order[0][column]": "2",
    "order[0][dir]": "desc",
    "start": "0",
    "length": "25",
    "search[value]": "",
    "search[regex]": "false",
    "status": "1",
}

headers = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.etenders.gov.za/Home/opportunities?id=1",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

with requests.Session() as s:
    # warm session first
    s.get("https://www.etenders.gov.za/Home/opportunities?id=1", headers=headers, timeout=60)
    r = s.get(URL, params=params, headers=headers, timeout=60)

print("FINAL URL:", r.url)
print("STATUS:", r.status_code)
print("CONTENT TYPE:", r.headers.get("content-type"))
print(r.text[:3000])

try:
    data = r.json()
    print("\nJSON KEYS:", data.keys())
    print("recordsTotal:", data.get("recordsTotal"))
    print("recordsFiltered:", data.get("recordsFiltered"))
    print("ROWS:", len(data.get("data", [])))

    for row in data.get("data", [])[:5]:
        print("\nROW:")
        print(json.dumps(row, indent=2)[:2000])
except Exception as e:
    print("\nJSON PARSE FAILED:", e)
