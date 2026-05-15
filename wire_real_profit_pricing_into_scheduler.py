from pathlib import Path
from datetime import datetime

TARGET = Path("app/services/safe_autonomous_scheduler_service.py")
IMPORT_LINE = "from app.services.real_profit_pricing_service import enrich_with_real_profit_pricing\n"

HELPER = """
def _apply_real_profit_fallback(tender: Dict[str, Any]) -> Dict[str, Any]:
    try:
        current_profit = _extract_numeric(tender.get("estimated_profit"))
        current_margin = _extract_numeric(tender.get("estimated_margin_percent") or tender.get("estimated_margin_pct"))

        if current_profit >= 30000 and current_margin >= 25:
            return {
                "status": "skipped_existing_pricing_ok",
                "priced": True,
                "estimated_profit": current_profit,
                "estimated_margin_percent": current_margin,
                "tender": tender,
            }

        real_profit = enrich_with_real_profit_pricing(tender)
        enriched = real_profit.get("payload") or tender

        return {
            "status": real_profit.get("status"),
            "method": "app.services.real_profit_pricing_service.enrich_with_real_profit_pricing",
            "priced": bool(real_profit.get("priced")),
            "estimated_profit": enriched.get("estimated_profit"),
            "estimated_margin_percent": enriched.get("estimated_margin_percent"),
            "tender": enriched,
            "real_profit_result": {k: v for k, v in real_profit.items() if k != "payload"},
        }
    except Exception as exc:
        return {
            "status": "real_profit_fallback_error",
            "priced": False,
            "error": str(exc),
            "tender": tender,
        }


"""


def main():
    if not TARGET.exists():
        raise FileNotFoundError(f"Missing {TARGET}")

    text = TARGET.read_text()

    backup = TARGET.with_suffix(TARGET.suffix + f".backup_before_real_profit_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    backup.write_text(text)
    print(f"Backup created: {backup}")

    if "from app.services.real_profit_pricing_service import enrich_with_real_profit_pricing" not in text:
        lines = text.splitlines(keepends=True)
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith("from ") or line.startswith("import "):
                insert_at = i + 1
        lines.insert(insert_at, IMPORT_LINE)
        text = "".join(lines)

    if "def _apply_real_profit_fallback" not in text:
        marker = "async def _production_check"
        idx = text.find(marker)
        if idx == -1:
            raise RuntimeError("Could not find async def _production_check marker.")
        text = text[:idx] + HELPER + text[idx:]

    old = """                decision = await _production_check(tender)
                item["production_decision"] = decision
"""

    new = """                real_profit_fallback = _apply_real_profit_fallback(tender)
                item["real_profit_fallback"] = {k: v for k, v in real_profit_fallback.items() if k != "tender"}
                tender = real_profit_fallback.get("tender") or tender

                decision = await _production_check(tender)
                item["production_decision"] = decision
"""

    if 'item["real_profit_fallback"]' not in text:
        if old not in text:
            raise RuntimeError("Could not find production_check block to patch.")
        text = text.replace(old, new, 1)

    TARGET.write_text(text)
    print("Real Profit Pricing fallback wired into safe scheduler.")


if __name__ == "__main__":
    main()
