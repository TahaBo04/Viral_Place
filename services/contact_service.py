from functools import lru_cache

import phonenumbers


@lru_cache(maxsize=1)
def country_catalog() -> list[dict]:
    items = []
    for region in sorted(phonenumbers.SUPPORTED_REGIONS):
        items.append({"region": region, "name": region, "dial_code": f"+{phonenumbers.country_code_for_region(region)}"})
    return items


def normalize_phone(value: str, region: str | None = None) -> str | None:
    try:
        parsed = phonenumbers.parse((value or "").strip(), region or None)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def phone_region(value: str, fallback: str | None = None) -> str | None:
    try:
        parsed = phonenumbers.parse(value or "", None)
    except phonenumbers.NumberParseException:
        return fallback
    return phonenumbers.region_code_for_number(parsed) or fallback


def national_phone(value: str) -> str:
    try:
        parsed = phonenumbers.parse(value or "", None)
    except phonenumbers.NumberParseException:
        return value or ""
    return str(parsed.national_number)
