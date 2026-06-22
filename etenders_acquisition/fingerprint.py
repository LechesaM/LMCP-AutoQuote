import hashlib


def build_fingerprint(title: str, url: str, closing_date: str | None) -> str:
    base = f"{title}|{url}|{closing_date or ''}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()
