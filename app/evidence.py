import json, os, hashlib
from datetime import datetime, timezone

EVIDENCE_DIR = os.getenv("EVIDENCE_DIR", "/evidence")

def ensure_dir():
    os.makedirs(EVIDENCE_DIR, exist_ok=True)

def write_evidence_pack(payload: dict) -> tuple[str, str]:
    """Write evidence JSON to disk and return (sha256, path)."""
    ensure_dir()
    raw = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    fn = f"evidence_{sha[:12]}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path = os.path.join(EVIDENCE_DIR, fn)
    with open(path, "wb") as f:
        f.write(raw)
    return sha, path
