import requests

URL = "https://www.etenders.gov.za/Home/opportunities"

headers = {
    "User-Agent": "Mozilla/5.0"
}

r = requests.get(URL, headers=headers)

print("STATUS:", r.status_code)
print("SIZE:", len(r.text))

# show first part
print("\n--- HTML PREVIEW ---\n")
print(r.text[:3000])

# search for clues
keywords = ["ajax", "json", "datatable", "opportunity", "api", "fetch"]

print("\n--- KEYWORD SCAN ---")
for k in keywords:
    print(k, "=>", k.lower() in r.text.lower())
