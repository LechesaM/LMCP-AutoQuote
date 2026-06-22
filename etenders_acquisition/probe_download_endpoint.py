import requests

GUID = "c71de4c8-2e6d-444d-b94b-10451f496058"
TENDER_ID = "159751"

URLS = [
    f"https://www.etenders.gov.za/Home/DownloadSpec?documentGuid={GUID}&source=sharepoint",
    f"https://www.etenders.gov.za/Home/DownloadSpec?documentGuid={GUID}",
    f"https://www.etenders.gov.za/Home/DownloadSpec?documentId={GUID}&source=sharepoint",
    f"https://www.etenders.gov.za/Home/DownloadSpec?documentId={GUID}",
    f"https://www.etenders.gov.za/Home/DownloadTenderDocument?documentGuid={GUID}&source=sharepoint",
    f"https://www.etenders.gov.za/Home/DownloadTenderDocument?documentId={GUID}",
    f"https://www.etenders.gov.za/Home/DownloadFile?documentGuid={GUID}",
    f"https://www.etenders.gov.za/Home/DownloadFile?documentId={GUID}",
    f"https://www.etenders.gov.za/Home/Download?documentGuid={GUID}",
    f"https://www.etenders.gov.za/Home/Download?documentId={GUID}",
    f"https://www.etenders.gov.za/Home/Download?blobName={GUID}",
    f"https://www.etenders.gov.za/Home/DownloadSpec?documentGuid={GUID}&tenderId={TENDER_ID}&source=sharepoint",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.etenders.gov.za/Home/opportunities",
}

for url in URLS:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True, stream=True)
        content_type = r.headers.get("content-type")
        content_length = r.headers.get("content-length")

        print()
        print("URL:", url)
        print("STATUS:", r.status_code)
        print("CONTENT_TYPE:", content_type)
        print("CONTENT_LENGTH:", content_length)
        print("FINAL_URL:", r.url)

        chunk = next(r.iter_content(chunk_size=64), b"")
        print("FIRST_BYTES:", chunk[:64])

    except Exception as e:
        print()
        print("URL:", url)
        print("ERROR:", e)
