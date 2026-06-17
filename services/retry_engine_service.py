import json
import os
from pathlib import Path
from datetime import datetime

RETRY_FILE = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "retry_engine" / "retry_queue.json"
RETRY_FILE.parent.mkdir(parents=True, exist_ok=True)

def _load():
    if not RETRY_FILE.exists():
        return []
    return json.loads(RETRY_FILE.read_text())

def _save(data):
    RETRY_FILE.write_text(json.dumps(data, indent=2))

def add_retry(item):
    queue = _load()
    item["retry_count"] = item.get("retry_count", 0) + 1
    item["last_retry"] = datetime.utcnow().isoformat()
    queue.append(item)
    _save(queue)

def get_retry_queue():
    return _load()
