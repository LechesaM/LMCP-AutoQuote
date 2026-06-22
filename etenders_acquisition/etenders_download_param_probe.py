import requests

BASE = "https://www.etenders.gov.za"
doc_id = "f329ec1e-7fd4-4245-af1d-3b7843d6cfaf"
tender_id = "159759"
filename = "RFQ number Tables 01.docx"

tests = [
    {"blobName": doc_id},
    {"blobname": doc_id},
    {"BlobName": doc_id},
    {"name": doc_id},
    {"documentName": filename},
    {"fileName": filename},
    {"filename": filename},
    {"path": filename},
    {"folder": tender_id, "fileName": filename},
    {"tenderId": tender_id, "fileName": filename},
    {"tendersID": tender_id, "fileName": filename},
    {"tenderId": tender_id, "blobName": doc_id},
    {"tendersID": tender_id, "blobName": doc_id},
]

s = requests.Session()
s.get(f"{BASE}/Home/opportunities?id=1", headers={"User-Agent": "Mozilla/5.0"}, timeout=60)

for params in tests:
    r = s.get(
        f"{BASE}/Home/Download",
        params=params,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": f"{BASE}/Home/opportunities?id=1",
            "Accept": "*/*",
        },
        timeout=30,
        allow_redirects=True,
    )

    print(params, "=>", r.status_code, r.headers.get("content-type"), len(r.content), r.url)
    print(r.content[:40].hex())
    print((r.headers.get("content-disposition") or "")[:200])
    print()
