from __future__ import annotations

import json

from app.services.csd_report_refresh_service import refresh_csd_registration_report


def main() -> int:
    result = refresh_csd_registration_report()
    print(json.dumps(result, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
