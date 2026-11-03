import re
from typing import Dict, Any, Tuple, Optional, List


# Список городов и ключевых населённых пунктов региона
KNOWN_PLACES = [
    "пенза", "кузнецк", "заречный", "сердобск", "каменка",
    "нижний ломов", "никольск", "белинский", "городище",
    "лунино", "мокроус", "мокшан", "пачелма", "земетчино",
    "башмаково", "шемышейка", "сосновоборск", "тамала",
    "вадинск", "конобеево", "воробьевка", "воробьёвка",
    "колышлей", "беково", "наровчат", "малая сердоба",
    "неверкино", "русский камешкир", "лопатино", "исса",
    "саратов", "саранск", "энгельс", "сызрань"
]

STREET_TYPES = [
    r"проспект", r"просп\.?", r"пр-т",
    r"улица", r"ул\.?",
    r"переулок", r"пер\.?",
    r"проезд", r"пр-д",
    r"шоссе", r"ш\.?",
    r"площадь", r"пл\.?",
    r"набережная", r"наб\.?",
    r"бульвар", r"бул\.?"
]


def normalize_text(text: str) -> str:
    """Приводит текст к нижнему регистру, правит частые опечатки и пробелы."""
    if not text:
        return ""
    text = str(text).strip().lower().replace("ё", "е")
    text = re.sub(r"\bизумркд", "изумруд", text)
    text = re.sub(r"\bстроит\w*", lambda m: "строителей" if "строит" in m.group(0) else m.group(0), text)
    return re.sub(r"\s+", " ", text)


def find_date(text: str) -> str:
    """Поиск упоминания даты поездки."""
    date_patterns = [
        r"\bсегодня\b",
        r"\bзавтра\b",
        r"\bпослезавтра\b",
        r"\b\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\b"
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).lower()
    return "не указана"


def find_time(text: str) -> str:
    """Поиск времени поездки."""
    match = re.search(r"(?:в\s+)?\b([01]?\d|2[0-3])[:.\s]([0-5]\d)\b", text, re.IGNORECASE)
    if match:
        return f"{match.group(1).zfill(2)}:{match.group(2)}"

    match_hour = re.search(r"(?:в\s+)?\b([01]?\d|2[0-3])\s*(?:час|часа|часов|ч)\b", text, re.IGNORECASE)
    if match_hour:
        return f"{match_hour.group(1).zfill(2)}:00"

    return "не указано"


def find_passengers(text: str) -> str:
    """Поиск количества пассажиров."""
    match = re.search(r"(\d+)\s*(?:чел|пасс|мест)", text, re.IGNORECASE)
    if match:
        return match.group(1)
    return "не указано"


def clean_address_part(address: Optional[str]) -> Optional[str]:
    """Очищает строку адреса от предлогов, знаков препинания и служебных слов."""
    if not address:
        return None

    cleaned = str(address).strip()
    cleaned = re.sub(r"^[,\s.:;—\-]+|[,\s.:;—\-]+$", "", cleaned)
    cleaned = re.sub(r"^(?:от|из|с|до|в|к|на)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\s+(?:сегодня|завтра|послезавтра|(?:в\s+)?\d{1,2}[:.\s]\d{2}|\d{1,2}[./]\d{1,2}).*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = cleaned.strip(" ,.-")
    return cleaned if cleaned else None


def parse_labeled_route(text: str) -> Optional[Dict[str, Any]]:
    """Парсинг структурированного формата: Откуда: ... Куда: ..."""
    match = re.search(
        r"откуда:\s*(.*?)\s*куда:\s*(.*?)(?=\s*(?:пассажиры|дата|время|тел|$):|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        from_raw = clean_address_part(match.group(1))
        to_raw = clean_address_part(match.group(2))
        return {
            "from_place": from_raw,
            "to_place": to_raw,
            "from_address": from_raw,
            "to_address": to_raw,
            "passengers": None,
            "date": None,
            "time": None,
        }
    return None


def parse_dash_route(text: str) -> Optional[Dict[str, Any]]:
    """Парсинг маршрута через тире или стрелку."""
    match = re.search(
        r"([а-яa-z0-9\s.,/]+?)\s*(?:—|-|->|=>)\s*([а-яa-z0-9\s.,/]+)",
        text,
        re.IGNORECASE,
    )
    if match:
        from_part = clean_address_part(match.group(1))
        to_part = clean_address_part(match.group(2))
        if from_part and to_part:
            return {
                "from_place": from_part,
                "to_place": to_part,
                "from_address": from_part,
                "to_address": to_part,
            }
    return None


def parse_direction_route(text: str) -> Optional[Dict[str, Any]]:
    """
    Парсинг маршрута по предлогам:
    1. 'от/из ... до/в/к/на ...'
    2. '... до/в/к/на ...' (например: 'кулакова 3 до улица правды')
    """
    # Вариант с парными предлогами
    match_pair = re.search(
        r"(?:от|из)\s+(.+?)\s+(?:до|в|к|на)\s+(.+)",
        text,
        re.IGNORECASE,
    )
    if match_pair:
        from_part = clean_address_part(match_pair.group(1))
        to_part = clean_address_part(match_pair.group(2))
        if from_part and to_part:
            return {
                "from_place": from_part,
                "to_place": to_part,
                "from_address": from_part,
                "to_address": to_part,
            }

    # Вариант с одиночным разделителем "до", "в", "к", "на"
    match_single = re.search(
        r"^(.+?)\s+\b(до|в|к|на)\b\s+(.+)$",
        text,
        re.IGNORECASE,
    )
    if match_single:
        from_part = clean_address_part(match_single.group(1))
        to_part = clean_address_part(match_single.group(3))
        if from_part and to_part:
            return {
                "from_place": from_part,
                "to_place": to_part,
                "from_address": from_part,
                "to_address": to_part,
            }

    return None


def parse_two_addresses_in_row(text: str) -> Optional[Dict[str, Any]]:
    """
    Парсит 2 адреса, идущих подряд без предлогов.
    Пример: 'изумрудная 9 проспект строителей 37'
    """
    house_regex = r"\d+(?:\s*[/к-]\s*\d+|[а-яa-z])?"
    type_pattern = "|".join(STREET_TYPES)

    m1 = re.search(
        rf"^(.+?\s+{house_regex})\s+((?:(?:{type_pattern})\s+).+)$",
        text,
        re.IGNORECASE
    )
    if m1:
        from_part = clean_address_part(m1.group(1))
        to_part = clean_address_part(m1.group(2))
        if from_part and to_part:
            return {
                "from_place": from_part,
                "to_place": to_part,
                "from_address": from_part,
                "to_address": to_part
            }

    m2 = re.search(
        rf"^([а-яa-z\s.,-]+?\s+{house_regex})\s+([а-яa-z\s.,-]+?\s+{house_regex})$",
        text,
        re.IGNORECASE
    )
    if m2:
        from_part = clean_address_part(m2.group(1))
        to_part = clean_address_part(m2.group(2))
        if from_part and to_part:
            return {
                "from_place": from_part,
                "to_place": to_part,
                "from_address": from_part,
                "to_address": to_part
            }

    return None


def find_place_positions(text: str) -> List[Dict[str, Any]]:
    """Находит позиции известных городов и населённых пунктов в тексте."""
    found = []
    norm = normalize_text(text)

    for place in KNOWN_PLACES:
        pattern = rf"\b{re.escape(place)}\b"
        for match in re.finditer(pattern, norm):
            found.append({
                "place": place.capitalize(),
                "start": match.start(),
                "end": match.end()
            })

    found.sort(key=lambda x: x["start"])
    return found


def find_direction(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Определяет маршрут между городами через пробел."""
    positions = find_place_positions(text)
    if len(positions) >= 2:
        return positions[0]["place"], positions[1]["place"]
    elif len(positions) == 1:
        return positions[0]["place"], None
    return None, None


async def parse_request(text: str) -> Dict[str, Any]:
    """Главная функция разбора текстового запроса клиента."""
    raw_text = "" if text is None else str(text)
    norm_text = normalize_text(raw_text)

    if not norm_text:
        return {
            "from_place": None,
            "to_place": None,
            "from_address": None,
            "to_address": None,
            "date": "не указана",
            "time": "не указано",
            "passengers": "не указано",
            "status": "локальный анализ",
        }

    date = find_date(norm_text)
    time = find_time(norm_text)
    passengers = find_passengers(norm_text)

    from_place: Optional[str] = None
    to_place: Optional[str] = None
    from_address: Optional[str] = None
    to_address: Optional[str] = None

    # 1. Структурированный ввод (Mini App / форма)
    labeled_result = parse_labeled_route(norm_text)

    if labeled_result:
        from_place = labeled_result["from_place"]
        to_place = labeled_result["to_place"]
        from_address = labeled_result["from_address"]
        to_address = labeled_result["to_address"]

        if labeled_result.get("passengers"):
            passenger_match = re.search(r"\d+", str(labeled_result["passengers"]))
            if passenger_match:
                passengers = passenger_match.group(0)

        if labeled_result.get("date"):
            date_val = str(labeled_result["date"]).strip()
            if date_val:
                date = date_val

        if labeled_result.get("time"):
            time_val = str(labeled_result["time"]).strip().lower()
            if time_val:
                parsed_time = find_time(time_val)
                time = parsed_time if parsed_time != "не указано" else time_val

    else:
        # 2. Направление по предлогам («кулакова 3 до улица правды» или «из Пензы в Кузнецк»)
        direction_result = parse_direction_route(norm_text)

        if direction_result:
            from_place = direction_result["from_place"]
            to_place = direction_result["to_place"]
            from_address = direction_result["from_address"]
            to_address = direction_result["to_address"]

        else:
            # 3. Маршрут через тире или стрелку
            dash_result = parse_dash_route(norm_text)

            if dash_result:
                from_place = dash_result["from_place"]
                to_place = dash_result["to_place"]
                from_address = dash_result["from_address"]
                to_address = dash_result["to_address"]

            else:
                # 4. Два адреса подряд внутри города
                two_addr_result = parse_two_addresses_in_row(norm_text)

                if two_addr_result:
                    from_place = two_addr_result["from_place"]
                    to_place = two_addr_result["to_place"]
                    from_address = two_addr_result["from_address"]
                    to_address = two_addr_result["to_address"]

                else:
                    # 5. Поиск городов по словарю ("пенза кузнецк")
                    from_place, to_place = find_direction(norm_text)
                    from_address = from_place
                    to_address = to_place

    # Заполнение пропусков
    if from_place and not from_address:
        from_address = from_place
    if to_place and not to_address:
        to_address = to_place

    if from_address:
        from_address = clean_address_part(from_address)
    if to_address:
        to_address = clean_address_part(to_address)

    if from_place and not from_address:
        from_address = from_place
    if to_place and not to_address:
        to_address = to_place

    result = {
        "from_place": from_place or "не определено",
        "to_place": to_place or "не определено",
        "from_address": from_address or "не указан",
        "to_address": to_address or "не указан",
        "date": date,
        "time": time,
        "passengers": passengers,
        "status": "локальный анализ",
    }

    print("----------------------------------------")
    print("ТЕКСТ КЛИЕНТА:")
    print(raw_text)
    print("ОТКУДА:", result["from_place"])
    print("КУДА:", result["to_place"])
    print("АДРЕС ОТКУДА:", result["from_address"])
    print("АДРЕС КУДА:", result["to_address"])
    print("ДАТА:", result["date"])
    print("ВРЕМЯ:", result["time"])
    print("ПАССАЖИРОВ:", result["passengers"])
    print("----------------------------------------")

    return result