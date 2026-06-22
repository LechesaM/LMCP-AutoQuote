import requests

doc_id = "f329ec1e-7fd4-4245-af1d-3b7843d6cfaf"
tender_id = "159759"

routes = [
    f"https://www.etenders.gov.za/Home/DownloadTenderDocument?documentId={doc_id}",
    f"https://www.etenders.gov.za/Home/DownloadTenderDocument?id={doc_id}",
    f"https://www.etenders.gov.za/Home/DownloadSupportDocument?documentId={doc_id}",
    f"https://www.etenders.gov.za/Home/DownloadSupportDocument?id={doc_id}",
    f"https://www.etenders.gov.za/Home/DownloadDocument?documentId={doc_id}",
    f"https://www.etenders.gov.za/Home/DownloadDocument?id={doc_id}",
    f"https://www.etenders.gov.za/Home/GetDocument?documentId={doc_id}",
    f"https://www.etenders.gov.za/Home/GetDocument?id={doc_id}",
    f"https://www.etenders.gov.za/Home/DownloadFile?documentId={doc_id}",
    f"https://www.etenders.gov.za/Home/DownloadFile?id={doc_id}",
    f"https://www.etenders.gov.za/Home/DownloadTenderDocument/{doc_id}",
    f"https://www.etenders.gov.za/Home/DownloadSupportDocument/{doc_id}",
    f"https://www.etenders.gov.za/Home/DownloadDocument/{doc_id}",
    f"https://www.etenders.gov.za/Home/GetDocument/{doc_id}",
    f"https://www.etenders.gov.za/Home/DownloadFile/{doc_id}",
    f"https://www.etenders.gov.za/Home/DownloadTenderDocument?tenderId={tender_id}&documentId={doc_id}",
    f"https://www.etenders.gov.za/Home/DownloadSupportDocument?tenderId={tender_id}&documentId={doc_id}",
]

s = requests.Session()
s.get(
    "https://www.etenders.gov.za/Home/opportunities?id=1",
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=60,
)

for url in routes:
    try:
        r = s.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.etenders.gov.za/Home/opportunities?id=1",
                "Accept": "*/*",
            },
            timeout=30,
            allow_redirects=True,
        )

        ct = r.headers.get("content-type")
        print(r.status_code, ct, len(r.content), url)
        print((r.content[:40] or b"").hex())
        print()
    except Exception as e:
        print("ERR", url, e)
