import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import inspect

from app.database import engine
from app.core.safe_loader import safe_import


logger = logging.getLogger(__name__)


REQUIRED_DIRS = [
    "app",
    "app/models",
    "app/services",
    "app/scripts",
]

REQUIRED_MODEL_EXPORTS = [
    ("app.models", "Opportunity"),
    ("app.models", "QuoteDraft"),
    ("app.models", "AuditLog"),
]

OPTIONAL_MODEL_EXPORTS = [
    ("app.models", "SupplierProduct"),
    ("app.models", "BuyerEvent"),
    ("app.models", "BuyerProfile"),
    ("app.models", "ProcurementSignal"),
]

REQUIRED_SERVICE_IMPORTS = [
    ("app.services.tender_harvester", None),
]

OPTIONAL_SERVICE_IMPORTS = [
    ("app.services.portal_registry", None),
    ("app.services.adaptive_crawler", None),
    ("app.services.national_portal_radar", None),
    ("app.services.procurement_intelligence.radar_pipeline", "process_buyer_intelligence"),
]


def _check_dirs() -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    for path_str in REQUIRED_DIRS:
        path = Path(path_str)
        results.append(
            {
                "name": path_str,
                "healthy": path.exists() and path.is_dir(),
                "detail": "directory exists" if path.exists() and path.is_dir() else "missing directory",
            }
        )

    return results


def _check_imports(items: List[tuple], required: bool) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    for module_path, attr_name in items:
        imported = safe_import(module_path, attr_name=attr_name, default=None)
        label = f"{module_path}.{attr_name}" if attr_name else module_path

        results.append(
            {
                "name": label,
                "healthy": imported is not None,
                "detail": "import ok" if imported is not None else ("required import failed" if required else "optional import unavailable"),
                "required": required,
            }
        )

    return results


def _check_database() -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        expected_tables = {
            "opportunities",
            "quote_drafts",
            "audit_logs",
        }

        optional_tables = {
            "supplier_products",
            "buyer_events",
            "buyer_profiles",
            "procurement_signals",
        }

        for table in sorted(expected_tables):
            results.append(
                {
                    "name": table,
                    "healthy": table in tables,
                    "detail": "table exists" if table in tables else "required table missing",
                    "required": True,
                }
            )

        for table in sorted(optional_tables):
            results.append(
                {
                    "name": table,
                    "healthy": table in tables,
                    "detail": "table exists" if table in tables else "optional table missing",
                    "required": False,
                }
            )

    except Exception as exc:
        results.append(
            {
                "name": "database_connection",
                "healthy": False,
                "detail": f"database inspection failed: {exc}",
                "required": True,
            }
        )

    return results


def run_system_guard() -> Dict[str, Any]:
    dir_checks = _check_dirs()
    required_import_checks = _check_imports(REQUIRED_MODEL_EXPORTS + REQUIRED_SERVICE_IMPORTS, required=True)
    optional_import_checks = _check_imports(OPTIONAL_MODEL_EXPORTS + OPTIONAL_SERVICE_IMPORTS, required=False)
    db_checks = _check_database()

    all_checks = dir_checks + required_import_checks + optional_import_checks + db_checks

    critical_failures = [
        check for check in all_checks
        if (not check.get("healthy")) and check.get("required", True)
    ]

    warnings = [
        check for check in all_checks
        if (not check.get("healthy")) and (not check.get("required", True))
    ]

    overall_healthy = len(critical_failures) == 0

    return {
        "healthy": overall_healthy,
        "critical_failure_count": len(critical_failures),
        "warning_count": len(warnings),
        "checks": all_checks,
    }


def log_system_guard_report() -> Dict[str, Any]:
    report = run_system_guard()

    if report["healthy"]:
        logger.info("SYSTEM_GUARD healthy with %s warning(s)", report["warning_count"])
    else:
        logger.warning(
            "SYSTEM_GUARD unhealthy: %s critical failure(s), %s warning(s)",
            report["critical_failure_count"],
            report["warning_count"],
        )

    for check in report["checks"]:
        level = logger.info if check["healthy"] else logger.warning
        level("SYSTEM_GUARD | %s | %s | %s", check["name"], check["healthy"], check["detail"])

    return report
