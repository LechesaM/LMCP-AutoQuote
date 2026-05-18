from __future__ import annotations

import json

from app.services.quote_review_service import backup_manual_review_assets


def main() -> int:
    result = backup_manual_review_assets()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
