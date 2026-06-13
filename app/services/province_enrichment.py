from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from app.services.procurement_intelligence.normalizer import normalize_province

PROVINCE_CODES = ("GP", "FS", "KZN", "WC", "EC", "NC", "NW", "MP", "LP")

_PROVINCE_NAME_TO_CODE = {
    "eastern cape": "EC",
    "free state": "FS",
    "gauteng": "GP",
    "kwa-zulu natal": "KZN",
    "kwazulu natal": "KZN",
    "kwazulu-natal": "KZN",
    "limpopo": "LP",
    "mpumalanga": "MP",
    "north west": "NW",
    "northern cape": "NC",
    "western cape": "WC",
}

_ENTITY_SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "lmcp_entity_master_seed.json"


def _clean_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s\-\/]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _province_code_from_text(text: str) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""

    normalized = normalize_province(cleaned)
    if normalized:
        mapped = _PROVINCE_NAME_TO_CODE.get(_clean_text(normalized))
        if mapped:
            return mapped

    for province_name, code in _PROVINCE_NAME_TO_CODE.items():
        if province_name in cleaned:
            return code

    if cleaned in PROVINCE_CODES:
        return cleaned

    return ""


@lru_cache(maxsize=1)
def _entity_alias_index() -> tuple[tuple[str, str], ...]:
    if not _ENTITY_SEED_PATH.exists():
        return ()

    aliases: list[tuple[str, str]] = []
    try:
        raw = json.loads(_ENTITY_SEED_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            for row in raw:
                if not isinstance(row, dict):
                    continue
                province = _province_code_from_text(row.get("province"))
                if not province:
                    continue
                for key in (
                    row.get("entity_name"),
                    row.get("entity_slug"),
                    row.get("buyer_class"),
                    row.get("entity_type"),
                ):
                    alias = _clean_text(key)
                    if alias:
                        aliases.append((alias, province))
    except Exception:
        return ()

    aliases.sort(key=lambda item: len(item[0]), reverse=True)
    return tuple(aliases)


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = _clean_text(value)
        if text:
            return text
    return ""


def infer_province_code(row: Mapping[str, Any] | None) -> str:
    if not isinstance(row, Mapping):
        return ""

    candidate_text = " ".join(
        part
        for part in (
            row.get("province"),
            row.get("buyer_province"),
            row.get("location"),
            row.get("region"),
            row.get("municipality"),
            row.get("department"),
            row.get("site"),
            row.get("site_location"),
            row.get("delivery_location"),
            row.get("buyer"),
            row.get("buyer_name"),
            row.get("entity_name"),
            row.get("issuer_name"),
            row.get("title"),
            row.get("description"),
            row.get("summary"),
            row.get("address"),
            row.get("city"),
            row.get("town"),
            row.get("source_name"),
        )
        if _clean_text(part)
    )

    direct = _province_code_from_text(candidate_text)
    if direct:
        return direct

    cleaned_text = _clean_text(candidate_text)
    if not cleaned_text:
        return ""

    for alias, province in _entity_alias_index():
        if alias and alias in cleaned_text:
            return province

    return ""


def infer_province_name(row: Mapping[str, Any] | None) -> str:
    code = infer_province_code(row)
    if not code:
        return ""
    for province_name, province_code in _PROVINCE_NAME_TO_CODE.items():
        if province_code == code:
            return normalize_province(province_name) or province_name.title()
    return code


def count_province_distribution(rows: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
    counts = {province: 0 for province in PROVINCE_CODES}
    for row in rows:
        code = infer_province_code(row)
        if code in counts:
            counts[code] += 1
    return counts
