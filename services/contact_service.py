import re


PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_phone(value: str) -> str | None:
    compact = re.sub(r"[\s().-]", "", (value or "").strip())
    if compact.startswith("00"):
        compact = "+" + compact[2:]
    return compact if PHONE_PATTERN.fullmatch(compact) else None
