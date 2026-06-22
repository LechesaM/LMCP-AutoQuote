import requests

BASE = "https://www.etenders.gov.za"

doc_id = "f329ec1e-7fd4-4245-af1d-3b7843d6cfaf"
tender_id = "159759"
filename = "RFQ number Tables 01.docx"

controllers = [
    "Home",
    "Tender",
    "Tenders",
    "Document",
    "Documents",
    "File",
    "Files",
]

actions = [
    "Download",
    "DownloadFile",
    "DownloadFiles",
    "DownloadDocument",
    "DownloadDocuments",
    "DownloadTenderDocument",
    "DownloadSupportDocument",
    "GetFile",
    "GetFiles",
    "GetDocument",
    "GetDocuments",
    "GetTenderDocument",
    "GetSupportDocument",
    "OpenDocument",
    "ViewDocument",
]

param_sets = [
    {"id": doc_id},
    {"documentId": doc_id},
    {"documentID": doc_id},
    {"supportDocumentId": doc_id},
    {"supportDocumentID": doc_id},
    {"fileId": doc_id},
    {"fileID": doc_id},
    {"guid": doc_id},
    {"tenderId": tender_id, "id": doc_id},
    {"tenderId": tender_id, "documentId": doc_id},
    {"tendersID": tender_id, "supportDocumentID": doc_id},
    {"tenderId": tender_id, "fileName": filename},
]

s = requests.Session()
headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": f"{BASE}/Home/opportunities?id=1",
    "Accept": "*/*",
}

s.get(f"{BASE}/Home/opportunities?id=1", headers=headers, timeout=60)

hits = []

for c in controllers:
    for a in actions:
        url = f"{BASE}/{c}/{a}"

        for params in param_sets:
            try:
                r = s.get(url, params=params, headers=headers, timeout=15, allow_redirects=False)
                ct = r.headers.get("content-type")
                size = len(r.content or b"")
                sig = (r.content[:8] or b"").hex()

                if r.status_code != 404:
                    line = {
                        "status": r.status_code,
                        "content_type": ct,
                        "size": size,
                        "sig": sig,
                        "url": r.url,
                    }
                    hits.append(line)
                    print(line)
            except Exception:
                pass

print("\nNON-404 HITS:", len(hits))
