import re


# ============================================================
# НАСЕЛЁННЫЕ ПУНКТЫ
# ============================================================

PLACES = {

    # Пензенская область

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

    # Саратовская область

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

    # Мордовия

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


# ============================================================
# ПОИСК НАСЕЛЁННЫХ ПУНКТОВ
# ============================================================

def find_places(text):
    """
    Ищет населённые пункты в тексте
    и возвращает уникальные места
    в порядке появления.
    """

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
                    PLACES[alias]
                )
            )

    matches.sort(
        key=lambda item: item[0]
    )

    result = []

    for start, end, place in matches:

        if place not in result:
            result.append(place)

    return result


# ============================================================
# ПОИСК ВСЕХ НАСЕЛЁННЫХ ПУНКТОВ
# ============================================================

def find_places_all(text):
    """
    Ищет все населённые пункты
    в порядке появления.

    Повторы сохраняются.
    """

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
                    PLACES[alias]
                )
            )

    matches.sort(
        key=lambda item: item[0]
    )

    result = []

    occupied_ranges = []

    for start, end, place in matches:

        overlap = False

        for old_start, old_end in occupied_ranges:

            if (
                start < old_end
                and end > old_start
            ):
                overlap = True
                break

        if overlap:
            continue

        result.append(place)

        occupied_ranges.append(
            (start, end)
        )

    return result


# ============================================================
# ПОСТРОЕНИЕ ШАБЛОНА НАСЕЛЁННЫХ ПУНКТОВ
# ============================================================

def get_place_pattern():

    aliases = sorted(
        PLACES.keys(),
        key=len,
        reverse=True
    )

    return "|".join(
        re.escape(alias)
        for alias in aliases
    )


# ============================================================
# ОПРЕДЕЛЕНИЕ НАПРАВЛЕНИЯ
# ============================================================

def find_direction(text):
    """
    Определяет откуда и куда едет пассажир.

    Поддерживает:

    Из Заречного в Пензу
    Из Пензы в Воробьевку
    Пенза в Заречный
    Пенза -> Воробьевка
    Пенза → Воробьевка
    Пенза - Воробьевка
    Пенза — Воробьевка
    Пенза Воробьевка
    Пенза Пенза
    """

    text_lower = text.lower()

    place_pattern = get_place_pattern()

    # --------------------------------------------------------
    # "из Заречного в Пензу"
    # --------------------------------------------------------

    pattern = (
        r"(?:из|с)\s+("
        + place_pattern
        + r")\s+"
        r"(?:в|до|на)\s+("
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

            return (
                from_place,
                to_place
            )

    # --------------------------------------------------------
    # "Пенза в Заречный"
    # --------------------------------------------------------

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

            return (
                from_place,
                to_place
            )

    # --------------------------------------------------------
    # "Пенза -> Воробьевка"
    # "Пенза → Воробьевка"
    # "Пенза - Воробьевка"
    # --------------------------------------------------------

    pattern = (
        r"\b("
        + place_pattern
        + r")"
        r"\s*(?:->|→|—|–|-)\s*"
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

            return (
                from_place,
                to_place
            )

    # --------------------------------------------------------
    # "Пенза Воробьевка"
    # --------------------------------------------------------

    pattern = (
        r"\b("
        + place_pattern
        + r")\s+("
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

            return (
                from_place,
                to_place
            )

    return None, None


# ============================================================
# ПРОВЕРКА: ЯВЛЯЕТСЯ ЛИ ФРАГМЕНТ НАСЕЛЁННЫМ ПУНКТОМ
# ============================================================

def contains_place_name(text):
    """
    Проверяет, содержит ли текст название
    населённого пункта.

    Используется при разборе адресов.

    Например:

    "Воробьевка 2"

    не должно считаться улицей в адресе Пензы,
    потому что Воробьевка — отдельный населённый пункт.
    """

    text_lower = text.lower().strip()

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

        if re.search(
            pattern,
            text_lower
        ):
            return True

    return False


# ============================================================
# ПОИСК АДРЕСОВ
# ============================================================

def clean_address(address):
    """
    Очищает адрес от лишних пробелов и знаков.
    """

    address = address.strip()

    address = re.sub(
        r"\s+",
        " ",
        address
    )

    address = re.sub(
        r"^[,\-—–:]+",
        "",
        address
    )

    address = re.sub(
        r"[,\-—–:]+$",
        "",
        address
    )

    return address.strip()


def find_address_parts(text):
    """
    Ищет конструкции:

    Пенза, улица Ленина, 25
    Пенза ул. Ленина 25
    Пенза, Ленина, 25
    Воробьевка, Советская, 10

    ВАЖНО:

    "Пенза Воробьевка 2 человека"

    НЕ считается адресом.

    В этом случае:

    Пенза -> населённый пункт
    Воробьевка -> населённый пункт
    2 -> пассажиры
    """

    text_clean = re.sub(
        r"\s+",
        " ",
        text.strip()
    )

    place_pattern = get_place_pattern()

    # --------------------------------------------------------
    # Ищем адрес с номером дома.
    #
    # Разрешены:
    #
    # Пенза Ленина 25
    # Пенза, Ленина, 25
    # Пенза улица Ленина 25
    # Пенза ул. Ленина 25
    # --------------------------------------------------------

    address_pattern = (
        r"("
        + place_pattern
        + r")"
        r"(?:\s*,?\s*)"
        r"(?:улица|ул\.?|проспект|пр-т|переулок|пер\.?|"
        r"шоссе|площадь|пл\.?|бульвар|бул\.?|"
        r"набережная|наб\.?|проезд|пр-д)?"
        r"\s*"
        r"([А-Яа-яЁёA-Za-z0-9.\- ]+?)"
        r"\s*,?\s*"
        r"(\d+[А-Яа-яA-Za-z]?)"
    )

    matches = list(
        re.finditer(
            address_pattern,
            text_clean,
            flags=re.IGNORECASE
        )
    )

    addresses = []

    for match in matches:

        place_alias = match.group(1).lower()

        place = PLACES.get(
            place_alias
        )

        street = match.group(2).strip()

        house = match.group(3).strip()

        if not place:
            continue

        # ----------------------------------------------------
        # КРИТИЧЕСКАЯ ПРОВЕРКА
        #
        # Если предполагаемая улица сама является
        # населённым пунктом, это НЕ адрес.
        #
        # Например:
        #
        # Пенза Воробьевка 2
        #
        # Старый код:
        # Пенза, Воробьевка, 2
        #
        # Новый код:
        # это НЕ адрес.
        # ----------------------------------------------------

        if contains_place_name(street):
            continue

        # ----------------------------------------------------
        # Убираем лишние слова в конце названия улицы
        # ----------------------------------------------------

        street = re.sub(
            r"\s+[,]+$",
            "",
            street
        ).strip()

        if not street:
            continue

        address = (
            f"{place}, "
            f"{street}, "
            f"{house}"
        )

        addresses.append(
            (
                match.start(),
                match.end(),
                address
            )
        )

    # --------------------------------------------------------
    # Убираем пересечения
    # --------------------------------------------------------

    result = []

    occupied_ranges = []

    for start, end, address in addresses:

        overlap = False

        for old_start, old_end in occupied_ranges:

            if (
                start < old_end
                and end > old_start
            ):
                overlap = True
                break

        if overlap:
            continue

        result.append(
            (
                start,
                end,
                clean_address(address)
            )
        )

        occupied_ranges.append(
            (start, end)
        )

    result.sort(
        key=lambda item: item[0]
    )

    if len(result) >= 2:

        return {
            "from_address": result[0][2],
            "to_address": result[1][2]
        }

    if len(result) == 1:

        return {
            "from_address": result[0][2],
            "to_address": None
        }

    return {
        "from_address": None,
        "to_address": None
    }


# ============================================================
# ОПРЕДЕЛЕНИЕ КОЛИЧЕСТВА ПАССАЖИРОВ
# ============================================================

def find_passengers(text):
    """
    Определяет количество пассажиров.

    Понимает:

    1 человек
    2 человека
    3 человека
    4 пассажира
    5 пассажиров
    2 пассажира
    3 чел
    3 чел.
    нас 3
    нас трое
    """

    text_lower = text.lower().strip()

    match = re.search(
        r"\b(\d+)\s*"
        r"(?:человек|человека|чел\.?|"
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

        if re.search(
            pattern,
            text_lower
        ):

            if (
                "человек" in text_lower
                or "пассажир" in text_lower
                or "нас " in text_lower
            ):

                return number

    return "не указано"


# ============================================================
# ОПРЕДЕЛЕНИЕ ВРЕМЕНИ
# ============================================================

def find_time(text):
    """
    Определяет время поездки.

    утром -> утро
    днем -> день
    днём -> день
    вечером -> вечер
    ночью -> ночь

    Также понимает:

    8:30
    18:45
    """

    text_lower = text.lower()

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

    match = re.search(
        r"\b\d{1,2}[:.]\d{2}\b",
        text_lower
    )

    if match:

        return match.group(0)

    return "не указано"


# ============================================================
# ОПРЕДЕЛЕНИЕ ДАТЫ
# ============================================================

def find_date(text):
    """
    Определяет относительную дату.
    """

    text_lower = text.lower()

    if "послезавтра" in text_lower:
        return "послезавтра"

    if "завтра" in text_lower:
        return "завтра"

    if "сегодня" in text_lower:
        return "сегодня"

    return "не указана"


# ============================================================
# ОСНОВНОЙ ПАРСЕР
# ============================================================

async def parse_request(text: str):

    # --------------------------------------------------------
    # Определяем направление
    # --------------------------------------------------------

    from_place, to_place = find_direction(
        text
    )

    # --------------------------------------------------------
    # Если направление не удалось определить
    # специальной конструкцией,
    # ищем все места в порядке появления.
    # --------------------------------------------------------

    if not from_place or not to_place:

        places = find_places_all(
            text
        )

        if not from_place and len(places) >= 1:
            from_place = places[0]

        if not to_place and len(places) >= 2:
            to_place = places[1]

    # --------------------------------------------------------
    # Определяем адреса
    # --------------------------------------------------------

    addresses = find_address_parts(
        text
    )

    from_address = addresses.get(
        "from_address"
    )

    to_address = addresses.get(
        "to_address"
    )

    # --------------------------------------------------------
    # Если адреса найдены,
    # используем их как точки маршрута.
    # --------------------------------------------------------

    route_from = (
        from_address
        or from_place
        or "не определено"
    )

    route_to = (
        to_address
        or to_place
        or "не определено"
    )

    # --------------------------------------------------------
    # Остальные параметры
    # --------------------------------------------------------

    date = find_date(
        text
    )

    time = find_time(
        text
    )

    passengers = find_passengers(
        text
    )

    # --------------------------------------------------------
    # Вывод в терминал
    # --------------------------------------------------------

    print(
        "----------------------------------------"
    )

    print(
        "ТЕКСТ КЛИЕНТА:"
    )

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
        "МАРШРУТ ОТКУДА:",
        route_from
    )

    print(
        "МАРШРУТ КУДА:",
        route_to
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

    print(
        "----------------------------------------"
    )

    # --------------------------------------------------------
    # Результат
    # --------------------------------------------------------

    return {

        "from": route_from,

        "to": route_to,

        "from_place": (
            from_place
            or "не определено"
        ),

        "to_place": (
            to_place
            or "не определено"
        ),

        "from_address": (
            from_address
            or "не указан"
        ),

        "to_address": (
            to_address
            or "не указан"
        ),

        "date": date,

        "time": time,

        "passengers": passengers,

        "status": "локальный анализ",
    }