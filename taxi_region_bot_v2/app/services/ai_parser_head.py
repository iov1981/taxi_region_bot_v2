
import re


PLACES = {
    "пенза": "Пенза",
    "пензы": "Пенза",
    "пензу": "Пенза",

    "кузнецк": "Кузнецк",
    "кузнецка": "Кузнецк",
    "кузнецку": "Кузнецк",

    "сердобск": "Сердобск",
    "сердобска": "Сердобск",
    "сердобску": "Сердобск",

    "каменка": "Каменка",
    "каменки": "Каменка",
    "каменку": "Каменка",

    "воробьевка": "Воробьевка",
    "воробьёвка": "Воробьевка",
    "воробьевку": "Воробьевка",
    "воробьёвку": "Воробьевка",

    "заречный": "Заречный",
    "заречного": "Заречный",
    "заречному": "Заречный",
    "заречном": "Заречный",

    "нижний ломов": "Нижний Ломов",
    "нижнего ломова": "Нижний Ломов",
    "нижнему ломову": "Нижний Ломов",

    "никольск": "Никольск",
    "никольска": "Никольск",
    "никольску": "Никольск",

    "саратов": "Саратов",
    "саратова": "Саратов",
    "саратову": "Саратов",

    "энгельс": "Энгельс",
    "энгельса": "Энгельс",
    "энгельсу": "Энгельс",

    "балаково": "Балаково",
    "балакова": "Балаково",

    "вольск": "Вольск",
    "вольска": "Вольск",

    "саранск": "Саранск",
    "саранска": "Саранск",
    "саранску": "Саранск",

    "рузаевка": "Рузаевка",
    "рузаевки": "Рузаевка",
    "рузаевку": "Рузаевка",

    "темников": "Темников",
    "темникова": "Темников",
    "темникову": "Темников",
}


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = str(text)

    text = text.replace("\u00a0", " ")
    text = text.replace("–", "—")
    text = text.replace("−", "—")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def get_house_pattern():
    return (
        r"\d+"
        r"(?:"
        r"\s*/\s*\d+"
        r"|"
        r"\s*-\s*\d+"
        r"|"
        r"\s*[кК]\s*\d+"
        r"|"
        r"\s*стр\.?\s*\d+"
        r"|"
        r"[А-Яа-яЁёA-Za-z]"
        r")?"
    )


def extract_house_number(text: str):
    if not text:
        return None

    text = normalize_text(text)

    pattern = get_house_pattern()

    matches = list(
        re.finditer(
            rf"(?<!\w)({pattern})(?!\w)",
            text
        )
    )

    for match in matches:
        value = match.group(1).strip()

        after = text[match.end():]

        # Не принимаем число перед "человек", "пассажиров" и т. п.
        if re.match(
            r"\s*(?:человек|человека|чел\.?|"
            r"пассажир|пассажира|пассажиров)\b",
            after,
            re.IGNORECASE
        ):
            continue

        return value

    return None


def normalize_house_number(house_number):
    if not house_number:
        return None

    value = str(house_number)

    value = value.replace(" ", "")
    value = value.replace("К", "к")
    value = value.replace("стр.", "стр")
    value = value.replace("Стр.", "стр")

    return value


def find_places(text):
    text = normalize_text(text)
    text_lower = text.lower()

    matches = []

    aliases = sorted(
        PLACES.keys(),
        key=len,
        reverse=True
    )

    for alias in aliases:
        pattern = (
            r"(?<![а-яё])"
            + re.escape(alias)
            + r"(?![а-яё])"
        )

        for match in re.finditer(
            pattern,
            text_lower
        ):
            matches.append(
                (
                    match.start(),
                    match.end(),
                    PLACES[alias],
                    alias
                )
            )

    matches.sort(
        key=lambda item: (
            item[0],
            -(item[1] - item[0])
        )
    )

    result = []

    for start, end, place, alias in matches:
        if place not in result:
            result.append(place)

    return result


def find_place_positions(text):
    text = normalize_text(text)
    text_lower = text.lower()

    matches = []

    aliases = sorted(
        PLACES.keys(),
        key=len,
        reverse=True
    )

    for alias in aliases:
        pattern = (
            r"(?<![а-яё])"
            + re.escape(alias)
            + r"(?![а-яё])"
        )

        for match in re.finditer(
            pattern,
            text_lower
        ):
            matches.append(
                {
                    "start": match.start(),
                    "end": match.end(),
                    "place": PLACES[alias],
                    "alias": alias,
                }
            )

    matches.sort(
        key=lambda item: (
            item["start"],
            -(item["end"] - item["start"])
        )
    )

    result = []
    occupied_until = -1

    for item in matches:
        if item["start"] < occupied_until:
            continue

        result.append(item)
        occupied_until = item["end"]

    return result


def remove_passenger_phrase(text: str) -> str:
    if not text:
        return ""

    result = normalize_text(text)

    patterns = [
        r"\b\d+\s*(?:человек|человека|чел\.?)\b",
        r"\b\d+\s*(?:пассажир|пассажира|пассажиров)\b",
        r"\bнас\s+\d+\b",
        r"\bнас\s+(?:двое|трое|четверо|пятеро|шестеро)\b",
        (
            r"\b(?:один|одна|двое|две|трое|три|четверо|"
            r"четыре|пятеро|пять|шестеро|шесть)"
            r"\s*(?:человек|человека|чел\.?|"
            r"пассажир|пассажира|пассажиров)\b"
        ),
    ]

    for pattern in patterns:
        result = re.sub(
            pattern,
            "",
            result,
            flags=re.IGNORECASE
        )

    result = re.sub(
        r",\s*,+",
        ",",
        result
    )

    result = re.sub(
        r"\s*,\s*$",
        "",
        result
    )

    result = re.sub(
        r"^\s*,\s*",
        "",
        result
    )

    return normalize_text(result)


def remove_date_time_phrases(text: str) -> str:
    """
    Удаляет дату и время из адресной части.

    Важно:
    конструкции вида:
        завтра в 9:00
        сегодня в 18:30
        послезавтра в 08:15
        в 10:00

    удаляются целиком вместе с предлогом "в",
    чтобы "в" не оставалась в адресе.
    """

    if not text:
        return ""

    result = normalize_text(text)

    # Сначала удаляем конструкции с точным временем.
    # Важно удалить вместе с "в":
    #
    # "завтра в 9:00"
    # "сегодня в 18:30"
    # "в 10:00"
    #
    # Также допускается "завтра, в 9:00".
    exact_time_patterns = [
        r"\b(?:сегодня|завтра|послезавтра)\s*,?\s+в\s+\d{1,2}[:.]\d{2}\b",
        r"\bв\s+\d{1,2}[:.]\d{2}\b",
        r"\b(?:сегодня|завтра|послезавтра)\s+\d{1,2}[:.]\d{2}\b",
    ]

    for pattern in exact_time_patterns:
        result = re.sub(
            pattern,
            "",
            result,
            flags=re.IGNORECASE
        )

    # Затем удаляем оставшиеся слова даты.
    date_patterns = [
        r"\bпослезавтра\b",
        r"\bзавтра\b",
        r"\bсегодня\b",
    ]

    for pattern in date_patterns:
        result = re.sub(
            pattern,
            "",
            result,
            flags=re.IGNORECASE
        )

    # Удаляем словесное время.
    time_patterns = [
        r"\bутром\b",
        r"\bутро\b",
        r"\bднём\b",
        r"\bднем\b",
        r"\bдень\b",
        r"\bвечером\b",
        r"\bвечер\b",
        r"\bночью\b",
        r"\bночь\b",
    ]

    for pattern in time_patterns:
        result = re.sub(
            pattern,
            "",
            result,
            flags=re.IGNORECASE
        )

    # Если где-то осталось отдельное "в" после удаления времени,
    # удаляем его только в конце адресной части.
    result = re.sub(
        r",\s*в\s*$",
        "",
        result,
        flags=re.IGNORECASE
    )

    result = re.sub(
        r"\s+в\s*$",
        "",
        result,
        flags=re.IGNORECASE
    )

    # Убираем лишние запятые и пробелы.
    result = re.sub(
        r",\s*,+",
        ",",
        result
    )

    result = re.sub(
        r"\s*,\s*$",
        "",
        result
    )

    result = re.sub(
        r"^\s*,\s*",
        "",
        result
    )

    result = re.sub(
        r"\s+",
        " ",
        result
    )

    return normalize_text(result)


def clean_address_part(text: str) -> str:
    if not text:
        return ""

    result = normalize_text(text)

    result = remove_passenger_phrase(result)
    result = remove_date_time_phrases(result)

    result = result.strip(" ,;.")

    result = re.sub(
        r"\s*,\s*",
        ", ",
        result
    )

    result = re.sub(
        r"\s+",
        " ",
        result
    )

    return result.strip()


def extract_address_from_segment(
    segment: str,
    place: str
):
    if not segment:
        return None

    segment = clean_address_part(segment)

    if not segment:
        return None

    place = place or ""

    aliases = sorted(
        [
            alias
            for alias, canonical in PLACES.items()
            if canonical == place
        ],
        key=len,
        reverse=True
    )

    cleaned = segment

    for alias in aliases:
        pattern = (
            r"(?<![а-яё])"
            + re.escape(alias)
            + r"(?![а-яё])"
        )

        match = re.search(
            pattern,
            cleaned.lower()
        )

        if match:
            before = cleaned[:match.start()]
            after = cleaned[match.end():]

            cleaned = before + " " + after
            break

    cleaned = cleaned.strip(" ,;.-")

    if not cleaned:
        return place

    cleaned = re.sub(
        r"\s*,\s*",
        ", ",
        cleaned
    )

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned
    ).strip()

    if cleaned.lower().startswith(
        place.lower()
    ):
        return cleaned

    return f"{place}, {cleaned}"


def find_direction(text):
    text = normalize_text(text)
    text_lower = text.lower()

    aliases = sorted(
        PLACES.keys(),
        key=len,
        reverse=True
    )

    place_pattern = "|".join(
        re.escape(alias)
        for alias in aliases
    )

    # Например:
    # из Пензы в Саратов
    # из Пензы до Саратова
    pattern = (
        r"(?:из|с)\s+("
        + place_pattern
        + r")\s+(?:в|до|на)\s+("
        + place_pattern
        + r")"
    )

    match = re.search(
        pattern,
        text_lower
    )

    if match:
        from_place = PLACES.get(
            match.group(1)
        )
        to_place = PLACES.get(
            match.group(2)
        )

        if from_place and to_place:
            return from_place, to_place

    # Например:
    # Пенза в Саратов
    pattern = (
        r"\b("
        + place_pattern
        + r")\s+"
        r"(?:в|до|на)\s+("
        + place_pattern
        + r")\b"
    )

    match = re.search(
        pattern,
        text_lower
    )

    if match:
        from_place = PLACES.get(
            match.group(1)
        )
        to_place = PLACES.get(
            match.group(2)
        )

        if from_place and to_place:
            return from_place, to_place

    # Например:
    # Пенза — Саратов
    # Пенза -> Саратов
    pattern = (
        r"\b("
        + place_pattern
        + r")"
        r"\s*(?:->|→|—|-)\s*"
        r"("
        + place_pattern
        + r")\b"
    )

    match = re.search(
        pattern,
        text_lower
    )

    if match:
        from_place = PLACES.get(
            match.group(1)
        )
        to_place = PLACES.get(
            match.group(2)
        )

        if from_place and to_place:
            return from_place, to_place

    return None, None


def split_route_by_dash(text: str):
    if not text:
        return None, None

    text = normalize_text(text)

    for separator in (
        "—",
        "–",
        "→",
        "->"
    ):
        if separator in text:
            parts = text.split(
                separator,
                1
            )

            if len(parts) == 2:
                left = parts[0].strip()
                right = parts[1].strip()

                if left and right:
                    return left, right

    match = re.search(
        r"\s+-\s+",
        text
    )

    if match:
        left = text[:match.start()].strip()
        right = text[match.end():].strip()

        if left and right:
            return left, right

    return None, None


def parse_dash_route(text: str):
    left, right = split_route_by_dash(text)

    if not left or not right:
        return None

    left_places = find_places(left)
    right_places = find_places(right)

    if not left_places or not right_places:
        return None

    from_place = left_places[0]
    to_place = right_places[0]

    from_address = extract_address_from_segment(
        left,
        from_place
    )

    to_address = extract_address_from_segment(
        right,
        to_place
    )

    return {
        "from_place": from_place,
        "to_place": to_place,
        "from_address": from_address,
        "to_address": to_address,
    }


def parse_route_by_places(text: str):
    positions = find_place_positions(text)

    if len(positions) < 2:
        return None

    first = positions[0]
    second = positions[1]

    from_place = first["place"]
    to_place = second["place"]

    first_segment = text[
        :second["start"]
    ].strip()

    second_segment = text[
        second["start"]:
    ].strip()

    from_address = extract_address_from_segment(
        first_segment,
        from_place
    )

    to_address = extract_address_from_segment(
        second_segment,
        to_place
    )

    return {
        "from_place": from_place,
        "to_place": to_place,
        "from_address": from_address,
        "to_address": to_address,
    }


def parse_direction_route(text: str):
    text_normalized = normalize_text(text)
    text_lower = text_normalized.lower()

    aliases = sorted(
        PLACES.keys(),
        key=len,
        reverse=True
    )

    place_pattern = "|".join(
        re.escape(alias)
        for alias in aliases
    )

    pattern = (
        r"(?:из|с)\s+("
        + place_pattern
        + r")"
        r"(.*?)"
        r"\s+(?:в|до|на)\s+("
        + place_pattern
        + r")"
        r"(.*)"
    )

    match = re.search(
        pattern,
        text_lower,
        flags=re.IGNORECASE
    )

    if not match:
        return None

    from_alias = match.group(1)
    middle = match.group(2)
    to_alias = match.group(3)
    tail = match.group(4)

    from_place = PLACES.get(
        from_alias
    )

    to_place = PLACES.get(
        to_alias
    )

    if not from_place or not to_place:
        return None

    from_segment = (
        from_place
        + " "
        + middle
    )

    to_segment = (
        to_place
        + " "
        + tail
    )

    return {
        "from_place": from_place,
        "to_place": to_place,
        "from_address": extract_address_from_segment(
            from_segment,
            from_place
        ),
        "to_address": extract_address_from_segment(
            to_segment,
            to_place
        ),
    }


def find_passengers(text):
    text_lower = normalize_text(text).lower()

    match = re.search(
        r"\b(\d+)\s*(?:человек|человека|чел\.?|"
        r"пассажир|пассажира|пассажиров)\b",
        text_lower
    )

    if match:
        return match.group(1)

    match = re.search(
        r"\bнас\s+(\d+)\b",
        text_lower
    )

    if match:
        return match.group(1)

    words = {
        "один": "1",
        "одна": "1",
        "двое": "2",
        "две": "2",
        "трое": "3",
        "три": "3",
        "четверо": "4",
        "четыре": "4",
        "пятеро": "5",
        "пять": "5",
        "шестеро": "6",
        "шесть": "6",
    }

    for word, number in words.items():
        pattern = (
            r"\b"
            + re.escape(word)
            + r"\b"
        )

        if not re.search(
            pattern,
            text_lower
        ):
            continue

        if (
            "человек" in text_lower
            or "пассажир" in text_lower
            or "нас " in text_lower
        ):
            return number

    return "не указано"


def find_time(text):
    text_lower = normalize_text(text).lower()

    match = re.search(
        r"\b\d{1,2}[:.]\d{2}\b",
        text_lower
    )

    if match:
        return match.group(0)

    if (
        "утро" in text_lower
        or "утром" in text_lower
    ):
        return "утро"

    if (
        "день" in text_lower
        or "днем" in text_lower
        or "днём" in text_lower
    ):
        return "день"

    if (
        "вечер" in text_lower
        or "вечером" in text_lower
    ):
        return "вечер"

    if (
        "ночь" in text_lower
        or "ночью" in text_lower
    ):
        return "ночь"

    return "не указано"


def find_date(text):
    text_lower = normalize_text(text).lower()

    if "послезавтра" in text_lower:
        return "послезавтра"

    if "завтра" in text_lower:
        return "завтра"

    if "сегодня" in text_lower:
        return "сегодня"

    return "не указана"


def find_addresses(
    text: str,
    from_place: str | None,
    to_place: str | None
):
    dash_result = parse_dash_route(text)

    if dash_result:
        if (
            not from_place
            or dash_result["from_place"] == from_place
        ) and (
            not to_place
            or dash_result["to_place"] == to_place
        ):
            return (
                dash_result["from_address"],
                dash_result["to_address"]
            )

    direction_result = parse_direction_route(text)

    if direction_result:
        return (
            direction_result["from_address"],
            direction_result["to_address"]
        )

    route_result = parse_route_by_places(text)

    if route_result:
        return (
            route_result["from_address"],
            route_result["to_address"]
        )

    if from_place:
        address = extract_address_from_segment(
            text,
            from_place
        )

        return address, None

    return None, None


async def parse_request(text: str):
    text = normalize_text(text)

    if not text:
        return {
            "from_place": None,
            "to_place": None,
            "from_address": None,
            "to_address": None,
            "date": "не указана",
            "time": "не указано",
            "passengers": "не указано",
        }

    date = find_date(text)
    time = find_time(text)
    passengers = find_passengers(text)

    from_place, to_place = find_direction(text)

    dash_result = parse_dash_route(text)

    if dash_result:
        from_place = dash_result["from_place"]
        to_place = dash_result["to_place"]

        from_address = dash_result["from_address"]
        to_address = dash_result["to_address"]

    else:
        direction_result = parse_direction_route(text)

        if direction_result:
            from_place = direction_result["from_place"]
            to_place = direction_result["to_place"]

            from_address = direction_result["from_address"]
            to_address = direction_result["to_address"]

        else:
            if not from_place or not to_place:
                places = find_places(text)

                if not from_place and len(places) >= 1:
                    from_place = places[0]

                if not to_place and len(places) >= 2:
                    to_place = places[1]

            from_address, to_address = find_addresses(
                text,
                from_place,
                to_place
            )

    if from_place and not from_address:
        from_address = from_place

    if to_place and not to_address:
        to_address = to_place

    if from_address:
        from_address = clean_address_part(
            from_address
        )

    if to_address:
        to_address = clean_address_part(
            to_address
        )

    if from_place and not from_address:
        from_address = from_place

    if to_place and not to_address:
        to_address = to_place

    print("----------------------------------------")
    print("ТЕКСТ КЛИЕНТА:")
    print(text)
    print()
    print(
        "ОТКУДА:",
        from_place or "не определено"
    )
    print(
        "КУДА:",
        to_place or "не определено"
    )
    print(
        "АДРЕС ОТКУДА:",
        from_address or "не указан"
    )
    print(
        "АДРЕС КУДА:",
        to_address or "не указан"
    )
    print(
        "ДАТА:",
        date
    )
    print(
        "ВРЕМЯ:",
        time
    )
    print(
        "ПАССАЖИРОВ:",
        passengers
    )
    print("----------------------------------------")

    return {
        "from_place": from_place or "не определено",
        "to_place": to_place or "не определено",
        "from_address": from_address or "не указан",
        "to_address": to_address or "не указан",
        "date": date,
        "time": time,
        "passengers": passengers,
        "status": "локальный анализ",
    }

