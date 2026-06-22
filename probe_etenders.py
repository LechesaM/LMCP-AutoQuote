import requests
import time
import socket
import ssl
from urllib.parse import urlparse


URLS = [
    "https://www.etenders.gov.za",
    "https://www.etenders.gov.za/Home/opportunities"
]


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def dns_check(host):
    start = time.time()
    try:
        ip = socket.gethostbyname(host)
        return {
            "host": host,
            "resolved_ip": ip,
            "dns_ms": int((time.time() - start) * 1000),
            "error": None
        }
    except Exception as e:
        return {
            "host": host,
            "resolved_ip": None,
            "dns_ms": None,
            "error": str(e)
        }


def tls_check(host):
    start = time.time()
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
        return {
            "tls_ms": int((time.time() - start) * 1000),
            "issuer": dict(cert.get("issuer", [])) if cert else None,
            "error": None
        }
    except Exception as e:
        return {
            "tls_ms": None,
            "error": str(e)
        }


def fetch(url):
    start = time.time()

    session = requests.Session()

    try:
        r = session.get(url, headers=HEADERS, timeout=20)

        text_snippet = r.text[:300].lower()

        failure_class = None

        # ---- BOT DETECTION SIGNALS ----
        if "captcha" in text_snippet:
            failure_class = "captcha_detected"
        elif "access denied" in text_snippet:
            failure_class = "access_denied"
        elif "cloudflare" in text_snippet:
            failure_class = "cloudflare_challenge"
        elif "request blocked" in text_snippet:
            failure_class = "request_blocked"
        elif r.status_code in (403, 401):
            failure_class = "forbidden"
        elif len(r.text) < 20000:
            failure_class = "suspiciously_small_payload"
        else:
            failure_class = None

        return {
            "url": url,
            "status": r.status_code,
            "content_type": r.headers.get("content-type"),
            "body_bytes": len(r.content),
            "total_ms": int((time.time() - start) * 1000),
            "success": failure_class is None,
            "failure_class": failure_class,
        }

    except requests.exceptions.RequestException as e:
        return {
            "url": url,
            "status": None,
            "error": str(e),
            "success": False,
            "failure_class": "network_error",
        }


def run():
    print("\n" + "=" * 80)
    print("ETENDERS FETCH DIAGNOSTICS (DETAILED)")
    print("=" * 80)

    host = urlparse(URLS[0]).hostname

    print("\n--- DNS CHECK ---")
    print(dns_check(host))

    print("\n--- TLS CHECK ---")
    print(tls_check(host))

    print("\n--- FETCH TESTS ---")

    for url in URLS:
        result = fetch(url)

        print("\n" + "-" * 80)
        print(url)
        print(result)


if __name__ == "__main__":
    run()
