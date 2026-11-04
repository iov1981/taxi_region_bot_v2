import re
from typing import Dict, Any, Optional


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = str(text).strip().lower()
    text = text.replace("ё", "е")
    # Отделяем знаки препинания от предлогов
    text = re.sub(r"[.,;:!?-]+(?=(до|в|на|к|от|из)\b)", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_date(text: str) -> str:
    date_patterns = [
        r"\bсегодня\b",
        r"\bзавтра\b",
        r"\bпослезавтра\b",
        r"\b\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\b"
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0).lower()
    return "не указана"


def find_time(text: str) -> str:
    if re.search(r"\bсейчас\b", text, flags=re.IGNORECASE):
        return "сейчас"
    if re.search(r"\bчерез\s+30\s+минут\b", text, flags=re.IGNORECASE):
        return "через 30 минут"
    if re.search(r"\bчерез\s+час\b", text, flags=re.IGNORECASE):
        return "через 1 час"

    match = re.search(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", text)
    if match:
        return f"{match.group(1)}:{match.group(2)}"
    return "не указано"


def find_passengers(text: str) -> str:
    match = re.search(r"(\d+)\s*(?:чел\w*|пасс\w*|мест\w*)?", text, flags=re.IGNORECASE)
    # Ищем конкретно привязку к пассажирам
    pass_match = re.search(r"(\d+)\s*(?:чел|пасс|мест)", text, flags=re.IGNORECASE)
    if pass_match:
        return pass_match.group(1)
    return "не указано"


def clean_address_part(part: str) -> str:
    """Очищает строку адреса от предлогов, времени, пассажиров и багажа."""
    if not part:
        return ""
    val = part.strip()

    # Срезаем начальные предлоги
    val = re.sub(r"^(?:от|из|до|в|на|к)\s+", "", val, flags=re.IGNORECASE)

    # Срезаем хвосты с доп. информацией
    val = re.sub(r",?\s*\d+\s*(?:человек\w*|чел\w*|пассажир\w*|мест\w*).*", "", val, flags=re.IGNORECASE)
    val = re.sub(r",?\s*(?:сейчас|сегодня|завтра|послезавтра|через\s+\d+\s+мин\w*).*", "", val, flags=re.IGNORECASE)
    val = re.sub(r",?\s*(?:есть\s+багаж|без\s+багажа|багаж).*", "", val, flags=re.IGNORECASE)
    val = re.sub(r",?\s*(?:нужно\s+детское\s+кресло|детское\s+кресло|кресло).*", "", val, flags=re.IGNORECASE)
    val = re.sub(r",?\s*(?:с\s+животными|без\s+животных|животные).*", "", val, flags=re.IGNORECASE)

    # Убираем запятые и пробелы по краям
    val = re.sub(r"^[,\.;:\s]+|[,\.;:\s]+$", "", val)
    return val.strip()


def parse_dash_route(text: str) -> Optional[Dict[str, str]]:
    match = re.search(r"^(.+?)\s*(?:—|-|->|=>)\s*(.+)$", text)
    if match:
        from_part = clean_address_part(match.group(1))
        to_part = clean_address_part(match.group(2))
        if from_part and to_part:
            return {
                "from_place": from_part,
                "to_place": to_part,
                "from_address": from_part,
                "to_address": to_part
            }
    return None


def parse_direction_route(text: str) -> Optional[Dict[str, str]]:
    match = re.search(r"(?:^|.*?)(?:от|из)?\s*(.+?)\s+(?:до|в|на|к)\s+(.+)", text, flags=re.IGNORECASE)
    if match:
        from_part = clean_address_part(match.group(1))
        to_part = clean_address_part(match.group(2))
        if from_part and to_part:
            return {
                "from_place": from_part,
                "to_place": to_part,
                "from_address": from_part,
                "to_address": to_part
            }
    return None


async def parse_request(text: str) -> Dict[str, Any]:
    raw_text = "" if text is None else str(text).strip()
    norm_text = normalize_text(raw_text)

    if not norm_text:
        return {
            "from_place": "не определено",
            "to_place": "не определено",
            "from_address": "не указан",
            "to_address": "не указан",
            "date": "не указана",
            "time": "не указано",
            "passengers": "не указано",
            "status": "локальный анализ"
        }

    date = find_date(norm_text)
    time = find_time(norm_text)
    passengers = find_passengers(norm_text)

    # 1. Проверяем формат через тире (А — Б, 2 человек...)
    route = parse_dash_route(norm_text)

    # 2. Если нет тире, проверяем по предлогам "от ... до ..." или "... до ..."
    if not route:
        route = parse_direction_route(norm_text)

    from_place = route["from_place"] if route else "не определено"
    to_place = route["to_place"] if route else "не определено"
    from_address = route["from_address"] if route else "не указан"
    to_address = route["to_address"] if route else "не указан"

    result = {
        "from_place": from_place,
        "to_place": to_place,
        "from_address": from_address,
        "to_address": to_address,
        "date": date,
        "time": time,
        "passengers": passengers if passengers != "не указано" else "1",
        "status": "локальный анализ"
    }

    print("----------------------------------------")
    print("ТЕКСТ КЛИЕНТА:", norm_text)
    print("ОТКУДА:", result["from_place"])
    print("КУДА:", result["to_place"])
    print("АДРЕС ОТКУДА:", result["from_address"])
    print("АДРЕС КУДА:", result["to_address"])
    print("ДАТА:", date)
    print("ВРЕМЯ:", time)
    print("ПАССАЖИРОВ:", result["passengers"])
    print("----------------------------------------")

    return result