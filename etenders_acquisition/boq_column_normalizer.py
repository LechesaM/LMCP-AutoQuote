import re


def normalize_numeric_token(token):
    if token is None:
        return None

    text = str(token)

    text = text.replace(",", "")
    text = text.strip()

    # reject scientific notation explosions
    if "E+" in text.upper():
        return None

    # reject absurd digit length
    digits = re.sub(r"[^\d]", "", text)

    if len(digits) > 10:
        return None

    try:
        value = float(text)

        if value > 100000000:
            return None

        return value

    except Exception:
        return None


def normalize_row(row):
    normalized = {}

    normalized["description"] = row.get("description")

    normalized["quantity"] = normalize_numeric_token(
        row.get("quantity")
    )

    normalized["unit_rate"] = normalize_numeric_token(
        row.get("unit_rate")
    )

    normalized["line_total"] = normalize_numeric_token(
        row.get("line_total")
    )

    return normalized
