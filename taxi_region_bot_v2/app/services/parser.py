import re
from typing import Dict, Any


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip().lower()
    text = re.sub(r"([а-яa-z0-9])\.(?=до|в|на|к)", r"\1 ", text)
    return re.sub(r"\s+", " ", text)


def find_date(text: str) -> str:
    date_patterns = [
        r"\bсегодня\b",
        r"\bзавтра\b",
        r"\bпослезавтра\b",
        r"\b\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\b"
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return "не указана"


def find_time(text: str) -> str:
    match = re.search(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", text)
    if match:
        return f"{match.group(1)}:{match.group(2)}"
    if "сейчас" in text:
        return "сейчас"
    return "не указано"


def find_passengers(text: str) -> int:
    match = re.search(r"(\d+)\s*(?:чел|пасс|мест|человек)", text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return 1
    return 1


def clean_address_part(address: str) -> str:
    if not address:
        return ""
    address = re.sub(r"^(?:от|до|из|в|к)\s+", "", address.strip())
    return address.strip()


def parse_order_text(text: str) -> Dict[str, Any]:
    raw_text = "" if text is None else str(text)
    norm = normalize_text(raw_text)

    date = find_date(norm)
    time = find_time(norm)
    passengers = find_passengers(norm)
    has_child_chair = "детск" in norm or "кресл" in norm

    from_address = None
    to_address = None

    dash_match = re.search(r"([а-яa-z0-9\s.,]+?)\s*(?:—|-|->|=>)\s*([а-яa-z0-9\s.,]+)", raw_text, flags=re.IGNORECASE)
    if dash_match:
        from_part = clean_address_part(dash_match.group(1))
        to_part = clean_address_part(dash_match.group(2))

        to_part = re.sub(r",?\s*\d+\s*(?:чел|пасс|человек).*", "", to_part, flags=re.IGNORECASE)
        to_part = re.sub(r",?\s*(?:сейчас|завтра|сегодня).*", "", to_part, flags=re.IGNORECASE)
        to_part = re.sub(r",?\s*нужно детское кресло.*", "", to_part, flags=re.IGNORECASE)

        from_address = from_part.strip()
        to_address = to_part.strip()
    else:
        dir_match = re.search(r"(?:от|из)\s+(.+?)\s+(?:до|в|к)\s+(.+)", raw_text, flags=re.IGNORECASE)
        if dir_match:
            from_address = clean_address_part(dir_match.group(1)).strip()
            to_address = clean_address_part(dir_match.group(2)).strip()

    return {
        "from_address": from_address,
        "to_address": to_address,
        "date": date,
        "time": time,
        "passengers": passengers,
        "has_child_chair": has_child_chair
    }