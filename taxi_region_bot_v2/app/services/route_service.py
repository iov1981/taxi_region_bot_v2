
import os
import re
import aiohttp

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# НАСТРОЙКИ
# ============================================================

ORS_API_KEY = os.getenv("ORS_API_KEY")
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")

MAX_ALLOWED_HOUSE_NUMBER = 999


print()
print("=" * 60)
print("ROUTE SERVICE V2.7")
print("ORS_API_KEY:", "OK" if ORS_API_KEY else "НЕТ")
print("GEOAPIFY_API_KEY:", "OK" if GEOAPIFY_API_KEY else "НЕТ")
print("MAX_ALLOWED_HOUSE_NUMBER:", MAX_ALLOWED_HOUSE_NUMBER)
print("=" * 60)


# ============================================================
# ОБЩИЕ ФУНКЦИИ
# ============================================================

def normalize_text(value):
    if value is None:
        return ""

    value = str(value).strip().lower()
    value = value.replace("ё", "е")
    value = re.sub(r"\s+", " ", value)

    return value


def normalize_street_name(value):
    value = normalize_text(value)

    # Типы улиц.
    value = re.sub(
        r"\b(?:улица|ул)\.?\b",
        " ",
        value
    )

    value = re.sub(
        r"\b(?:проспект|просп|пр-т)\.?\b",
        " ",
        value
    )

    value = re.sub(
        r"\b(?:переулок|пер)\.?\b",
        " ",
        value
    )

    value = re.sub(
        r"\b(?:шоссе|ш)\.?\b",
        " ",
        value
    )

    value = re.sub(
        r"\b(?:площадь|пл)\.?\b",
        " ",
        value
    )

    value = re.sub(
        r"\b(?:бульвар|бул)\.?\b",
        " ",
        value
    )

    value = re.sub(
        r"\b(?:набережная|наб)\.?\b",
        " ",
        value
    )

    value = re.sub(
        r"\b(?:проезд|пр-д)\.?\b",
        " ",
        value
    )

    value = re.sub(
        r"[,\.;:]",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


def normalize_house_number(value):
    if value is None:
        return ""

    value = str(value).strip().lower()
    value = re.sub(r"\s+", "", value)

    value = value.replace("корпус", "к")
    value = value.replace("корп.", "к")
    value = value.replace("корп", "к")

    value = value.replace("строение", "стр")
    value = value.replace("ст.", "стр")

    return value


# ============================================================
# НОМЕР ДОМА
# ============================================================

def get_house_pattern():
    """
    Поддерживаем:

        10
        10А
        10а
        25/1
        25-27
        25к1
        25 к 1
        25стр1
        25 стр 1
    """

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


def extract_house_number(address):
    if not address:
        return None

    pattern = get_house_pattern()

    match = re.search(
        rf"(?<!\d)({pattern})(?!\d)",
        str(address),
        flags=re.IGNORECASE
    )

    if not match:
        return None

    return normalize_house_number(
        match.group(1)
    )


def has_house_number(address):
    return extract_house_number(address) is not None


def get_main_house_number(house_number):
    if not house_number:
        return None

    match = re.match(
        r"(\d+)",
        normalize_house_number(house_number)
    )

    if not match:
        return None

    return int(match.group(1))


def is_house_number_allowed(house_number):
    main_number = get_main_house_number(
        house_number
    )

    if main_number is None:
        return False

    return main_number <= MAX_ALLOWED_HOUSE_NUMBER


# ============================================================
# УЛИЦА
# ============================================================

def extract_street_name(address):
    """
    Извлекает название улицы.

    Примеры:

        Пенза, Московская, 29
        -> московская

        Пенза, улица Московская, 29
        -> московская

        Пенза, ул. Московская, 29
        -> московская

        Пенза, проспект Победы, 10
        -> победы

        Пенза
        -> None
    """

    if not address:
        return None

    text = str(address).strip()

    # --------------------------------------------------------
    # Удаляем номер дома.
    # --------------------------------------------------------

    house = extract_house_number(text)

    if house:
        pattern = get_house_pattern()

        text_without_house = re.sub(
            rf"(?<!\d){pattern}(?!\d)",
            "",
            text,
            count=1,
            flags=re.IGNORECASE
        )
    else:
        text_without_house = text

    text_without_house = re.sub(
        r"\s+",
        " ",
        text_without_house
    ).strip(" ,;.")

    if not text_without_house:
        return None

    # --------------------------------------------------------
    # Известные населённые пункты.
    # --------------------------------------------------------

    known_places = {
        "пенза",
        "саратов",
        "заречный",
        "воробьевка",
        "воробьевку",
        "воробьёвка",
        "воробьёвку",
        "кузнецк",
        "сердобск",
        "каменка",
        "нижний ломов",
        "никольск",
        "энгельс",
        "балаково",
        "вольск",
        "саранск",
        "рузаевка",
        "темников",
    }

    parts = [
        part.strip()
        for part in re.split(
            r",",
            text_without_house
        )
        if part.strip()
    ]

    # --------------------------------------------------------
    # Формат:
    #
    # Пенза, улица Комсомольская
    # --------------------------------------------------------

    if len(parts) >= 2:

        for part in reversed(parts):

            normalized = normalize_text(part)

            if normalized in known_places:
                continue

            street = normalize_street_name(part)

            if street:
                return street

        return None

    # --------------------------------------------------------
    # Формат:
    #
    # Пенза улица Комсомольская
    # --------------------------------------------------------

    only_part = normalize_text(
        parts[0] if parts else text_without_house
    )

    for place in sorted(
        known_places,
        key=len,
        reverse=True
    ):

        pattern = (
            r"^"
            + re.escape(place)
            + r"(?:\s+|,\s*)"
        )

        only_part = re.sub(
            pattern,
            "",
            only_part,
            flags=re.IGNORECASE
        )

    street = normalize_street_name(
        only_part
    )

    if not street:
        return None

    return street


def streets_match(requested_street, found_street):
    requested = normalize_street_name(
        requested_street
    )

    found = normalize_street_name(
        found_street
    )

    if not requested or not found:
        return False

    if requested == found:
        return True

    if requested in found:
        return True

    if found in requested:
        return True

    return False


# ============================================================
# НАСЕЛЁННЫЙ ПУНКТ
# ============================================================

def extract_locality_from_address(address):
    if not address:
        return None

    text = normalize_text(address)

    known_places = (
        "пенза",
        "саратов",
        "заречный",
        "воробьевка",
        "воробьевку",
        "воробьёвка",
        "воробьёвку",
        "кузнецк",
        "сердобск",
        "каменка",
        "нижний ломов",
        "никольск",
        "энгельс",
        "балаково",
        "вольск",
        "саранск",
        "рузаевка",
        "темников",
    )

    for place in sorted(
        known_places,
        key=len,
        reverse=True
    ):

        if place in text:

            if "воробьев" in place:
                return "воробьевка"

            if "воробьёв" in place:
                return "воробьевка"

            return place

    return None


def get_result_locality(properties):
    if not properties:
        return ""

    fields = (
        "city",
        "town",
        "village",
        "municipality",
        "county",
        "locality",
    )

    for field in fields:

        value = properties.get(field)

        if value:
            return normalize_text(value)

    return ""


def locality_matches(
    requested_locality,
    properties
):
    if not requested_locality:
        return True

    requested = normalize_text(
        requested_locality
    )

    found = get_result_locality(
        properties
    )

    if not found:
        return False

    if requested == found:
        return True

    if requested in found:
        return True

    if found in requested:
        return True

    return False


# ============================================================
# РЕГИОН
# ============================================================

def normalize_region(value):
    value = normalize_text(value)

    value = value.replace(
        "область",
        ""
    ).strip()

    return value


def region_matches(
    requested_region,
    properties
):
    if not requested_region:
        return True

    requested = normalize_region(
        requested_region
    )

    found = (
        properties.get("state")
        or properties.get("region")
    )

    if not found:
        return False

    found = normalize_region(found)

    return (
        requested == found
        or requested in found
        or found in requested
    )


def detect_region(address):
    text = normalize_text(address)

    if (
        "пенза" in text
        or "заречн" in text
        or "воробьев" in text
        or "воробьёв" in text
    ):
        return "Пензенская область"

    if (
        "саратов" in text
        or "энгельс" in text
        or "балаково" in text
        or "вольск" in text
    ):
        return "Саратовская область"

    if (
        "саранск" in text
        or "рузаев" in text
        or "темников" in text
    ):
        return "Республика Мордовия"

    return None


# ============================================================
# GEOAPIFY
# ============================================================

async def geoapify_request(
    text,
    bias_lat=None,
    bias_lon=None
):
    if not GEOAPIFY_API_KEY:

        print(
            "❌ GEOAPIFY_API_KEY отсутствует"
        )

        return []

    url = (
        "https://api.geoapify.com/"
        "v1/geocode/search"
    )

    params = {
        "text": text,
        "apiKey": GEOAPIFY_API_KEY,
        "limit": 5,
        "lang": "ru",
    }

    if (
        bias_lat is not None
        and bias_lon is not None
    ):

        params["bias"] = (
            f"proximity:"
            f"{bias_lon},"
            f"{bias_lat}"
        )

    try:

        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(
                    total=20
                )
            ) as response:

                print(
                    "GEOAPIFY HTTP:",
                    response.status
                )

                if response.status != 200:

                    body = await response.text()

                    print(
                        "GEOAPIFY RESPONSE:"
                    )

                    print(
                        body[:1000]
                    )

                    return []

                data = await response.json()

                features = data.get(
                    "features",
                    []
                )

                print(
                    "GEOAPIFY найдено результатов:",
                    len(features)
                )

                return features

    except Exception as error:

        print(
            "❌ Ошибка запроса Geoapify:",
            repr(error)
        )

        return []


# ============================================================
# ДАННЫЕ GEOAPIFY
# ============================================================

def get_found_house(properties):
    if not properties:
        return None

    house = (
        properties.get("housenumber")
        or properties.get("house_number")
        or properties.get("street_number")
    )

    if house is None:
        return None

    return normalize_house_number(
        house
    )


def get_found_street(properties):
    if not properties:
        return None

    return (
        properties.get("street")
        or properties.get("street_name")
        or properties.get("name")
    )


def get_result_type(properties):
    if not properties:
        return ""

    return normalize_text(
        properties.get("result_type")
        or properties.get("type")
        or ""
    )


# ============================================================
# ПРОВЕРКА ТОЧНОГО АДРЕСА
# ============================================================

def exact_address_match(
    properties,
    requested_locality,
    requested_region,
    requested_street,
    requested_house
):
    if not properties:
        return False

    found_house = get_found_house(
        properties
    )

    found_street = get_found_street(
        properties
    )

    result_type = get_result_type(
        properties
    )

    print(
        "  Найден тип:",
        result_type
    )

    print(
        "  Найдена улица:",
        found_street
    )

    print(
        "  Найден дом:",
        found_house
    )

    # ========================================================
    # НОМЕР ДОМА
    # ========================================================

    if requested_house:

        if not found_house:

            print(
                "  ❌ Geoapify не вернул "
                "номер дома."
            )

            return False

        if (
            normalize_house_number(
                requested_house
            )
            !=
            normalize_house_number(
                found_house
            )
        ):

            print(
                "  ❌ Номер дома НЕ совпадает."
            )

            return False

        print(
            "  ✅ Номер дома совпадает."
        )

    # ========================================================
    # УЛИЦА
    # ========================================================

    if requested_street:

        if not found_street:

            print(
                "  ❌ Geoapify не вернул "
                "улицу."
            )

            return False

        if not streets_match(
            requested_street,
            found_street
        ):

            print(
                "  ❌ Улица НЕ совпадает."
            )

            return False

        print(
            "  ✅ Улица совпадает."
        )

    # ========================================================
    # НАСЕЛЁННЫЙ ПУНКТ
    # ========================================================

    if requested_locality:

        if not locality_matches(
            requested_locality,
            properties
        ):

            print(
                "  ❌ Населённый пункт "
                "НЕ совпадает."
            )

            return False

        print(
            "  ✅ Населённый пункт совпадает."
        )

    # ========================================================
    # РЕГИОН
    # ========================================================

    if requested_region:

        if not region_matches(
            requested_region,
            properties
        ):

            print(
                "  ❌ Регион НЕ совпадает."
            )

            return False

        print(
            "  ✅ Регион совпадает."
        )

    # ========================================================
    # BUILDING
    # ========================================================

    if result_type == "building":

        print(
            "  ✅ RESULT_TYPE = BUILDING."
        )

        return True

    # ========================================================
    # ДОМ
    # ========================================================

    if requested_house:

        if (
            found_house
            and requested_street
            and found_street
        ):

            print(
                "  ✅ Адрес подтверждён "
                "по улице + номеру дома."
            )

            return True

        print(
            "  ❌ Недостаточно данных "
            "для подтверждения дома."
        )

        return False

    # ========================================================
    # УЛИЦА БЕЗ ДОМА
    # ========================================================

    if requested_street:

        print(
            "  ✅ Адрес без номера дома "
            "подтверждён по улице."
        )

        return True

    # ========================================================
    # ТОЛЬКО НАСЕЛЁННЫЙ ПУНКТ
    # ========================================================

    if requested_locality:

        print(
            "  ✅ Населённый пункт "
            "подтверждён."
        )

        return True

    return False


# ============================================================
# ПОИСК ЦЕНТРА НАСЕЛЁННОГО ПУНКТА
# ============================================================

async def geocode_locality_center(
    locality,
    region=None
):
    if not locality:
        return None

    locality = normalize_text(
        locality
    )

    queries = []

    if region:

        queries.append(
            f"{locality}, {region}, Россия"
        )

    queries.append(
        f"{locality}, Россия"
    )

    bias_coordinates = {
        "пенза": (53.1959, 45.0183),
        "саратов": (51.5336, 46.0343),
        "заречный": (53.2000, 45.1667),
        "воробьевка": (53.1000, 44.9000),
    }

    bias_lat = None
    bias_lon = None

    if locality in bias_coordinates:

        bias_lat, bias_lon = (
            bias_coordinates[locality]
        )

    for query in queries:

        print()
        print(
            "GEOAPIFY FALLBACK:"
        )

        print(
            "  Населённый пункт:",
            locality
        )

        print(
            "  Запрос:",
            query
        )

        features = await geoapify_request(
            query,
            bias_lat=bias_lat,
            bias_lon=bias_lon
        )

        for index, feature in enumerate(
            features,
            start=1
        ):

            properties = (
                feature.get("properties")
                or {}
            )

            geometry = (
                feature.get("geometry")
                or {}
            )

            coordinates = geometry.get(
                "coordinates"
            )

            print()
            print(
                f"FALLBACK КАНДИДАТ: {index}"
            )

            print(
                "  Адрес:",
                properties.get(
                    "formatted"
                )
            )

            print(
                "  Тип:",
                properties.get(
                    "result_type"
                )
            )

            print(
                "  Город:",
                properties.get("city")
            )

            print(
                "  Регион:",
                properties.get("state")
                or properties.get("region")
            )

            if not locality_matches(
                locality,
                properties
            ):

                print(
                    "  ❌ Населённый пункт "
                    "не совпадает."
                )

                continue

            if not coordinates:

                print(
                    "  ❌ Нет координат."
                )

                continue

            if len(coordinates) < 2:

                print(
                    "  ❌ Некорректные координаты."
                )

                continue

            lon = coordinates[0]
            lat = coordinates[1]

            print(
                "  ✅ Центр населённого пункта "
                "подтверждён."
            )

            print(
                "  Координаты:",
                lat,
                lon
            )

            return {
                "lat": lat,
                "lon": lon,
                "formatted": properties.get(
                    "formatted"
                ),
                "properties": properties,
            }

    print()
    print(
        "❌ Центр населённого пункта "
        "не найден."
    )

    return None


# ============================================================
# ТОЧНОЕ ГЕОКОДИРОВАНИЕ
# ============================================================

async def geocode_exact_address(address):

    print()
    print("=" * 60)
    print(
        "ГЕОКОДИРОВАНИЕ:",
        address
    )
    print("=" * 60)

    if not address:

        print(
            "❌ Пустой адрес."
        )

        return None

    requested_locality = (
        extract_locality_from_address(
            address
        )
    )

    requested_region = detect_region(
        address
    )

    requested_house = extract_house_number(
        address
    )

    requested_street = extract_street_name(
        address
    )

    print(
        "Населённый пункт:",
        requested_locality
    )

    print(
        "Регион:",
        requested_region
    )

    print(
        "Улица:",
        requested_street
    )

    print(
        "Номер дома:",
        requested_house
    )

    # ========================================================
    # ЗАЩИТА НОМЕРА ДОМА
    # ========================================================

    if requested_house:

        print(
            "Ищем ТОЛЬКО точный адрес."
        )

        if not is_house_number_allowed(
            requested_house
        ):

            print()
            print(
                "❌ НОМЕР ДОМА СЛИШКОМ БОЛЬШОЙ:"
            )

            print(
                requested_house
            )

            print(
                "❌ Максимально разрешённый:",
                MAX_ALLOWED_HOUSE_NUMBER
            )

            print(
                "❌ Геокодирование прекращено."
            )

            return None

    else:

        print(
            "ℹ️ Номер дома не указан."
        )

    # ========================================================
    # BIAS
    # ========================================================

    bias_coordinates = {
        "пенза": (53.1959, 45.0183),
        "саратов": (51.5336, 46.0343),
        "заречный": (53.2000, 45.1667),
        "воробьевка": (53.1000, 44.9000),
    }

    bias_lat = None
    bias_lon = None

    if requested_locality:

        coords = bias_coordinates.get(
            requested_locality
        )

        if coords:
            bias_lat, bias_lon = coords

    # ========================================================
    # ЗАПРОСЫ
    # ========================================================

    queries = []

    queries.append(
        str(address).strip()
    )

    # --------------------------------------------------------
    # Улица без дома.
    # --------------------------------------------------------

    if (
        requested_street
        and not requested_house
        and requested_locality
    ):

        street_query = (
            f"{requested_locality}, "
            f"{requested_street}"
        )

        queries.append(
            street_query
        )

    # --------------------------------------------------------
    # Улица + дом.
    # --------------------------------------------------------

    if (
        requested_street
        and requested_house
    ):

        second_query = (
            f"{requested_locality or ''}, "
            f"{requested_street}, "
            f"{requested_house}, "
            f"{requested_region or ''}, "
            f"Россия"
        )

        second_query = re.sub(
            r"\s+",
            " ",
            second_query
        ).strip(" ,")

        if (
            second_query.lower()
            != str(address).strip().lower()
        ):

            queries.append(
                second_query
            )

    # --------------------------------------------------------
    # Убираем дубли.
    # --------------------------------------------------------

    unique_queries = []

    for query in queries:

        if not query:
            continue

        if query.lower() in [
            item.lower()
            for item in unique_queries
        ]:

            continue

        unique_queries.append(
            query
        )

    # ========================================================
    # GEOAPIFY
    # ========================================================

    for index, query in enumerate(
        unique_queries,
        start=1
    ):

        print()
        print(
            f"GEOAPIFY ПОИСК № {index}"
        )

        print(
            "  text:",
            query
        )

        if (
            bias_lat is not None
            and bias_lon is not None
        ):

            print(
                "  bias:",
                bias_lat,
                bias_lon
            )

        features = await geoapify_request(
            query,
            bias_lat=bias_lat,
            bias_lon=bias_lon
        )

        for candidate_index, feature in enumerate(
            features,
            start=1
        ):

            properties = (
                feature.get("properties")
                or {}
            )

            geometry = (
                feature.get("geometry")
                or {}
            )

            coordinates = geometry.get(
                "coordinates"
            )

            print()
            print(
                f"GEOAPIFY КАНДИДАТ: "
                f"{candidate_index}"
            )

            print(
                "  Адрес:",
                properties.get(
                    "formatted"
                )
            )

            print(
                "  Тип:",
                properties.get(
                    "result_type"
                )
            )

            print(
                "  Город:",
                properties.get("city")
            )

            print(
                "  Населённый пункт:",
                properties.get("locality")
                or properties.get("town")
                or properties.get("village")
            )

            print(
                "  Улица:",
                properties.get("street")
            )

            print(
                "  Дом:",
                properties.get("housenumber")
            )

            print(
                "  confidence:",
                properties.get("confidence")
            )

            print(
                "  building confidence:",
                properties.get(
                    "building_confidence"
                )
            )

            print(
                "  Регион результата:",
                properties.get("state")
                or properties.get("region")
            )

            print(
                "  result_type:",
                properties.get(
                    "result_type"
                )
            )

            print(
                "  match_type:",
                properties.get(
                    "match_type"
                )
            )

            matched = exact_address_match(
                properties=properties,
                requested_locality=requested_locality,
                requested_region=requested_region,
                requested_street=requested_street,
                requested_house=requested_house
            )

            if not matched:
                continue

            if (
                not coordinates
                or len(coordinates) < 2
            ):

                print(
                    "  ❌ Нет координат."
                )

                continue

            lon = coordinates[0]
            lat = coordinates[1]

            print()
            print(
                "  ✅ АДРЕС ПОДТВЕРЖДЁН."
            )

            print(
                "  Координаты:",
                lat,
                lon
            )

            return {
                "lat": lat,
                "lon": lon,
                "formatted": properties.get(
                    "formatted"
                ),
                "properties": properties,
            }

    # ========================================================
    # ДОМ — FALLBACK ЗАПРЕЩЁН
    # ========================================================

    if requested_house:

        print()
        print(
            "❌ GEOAPIFY не подтвердил "
            "точный адрес."
        )

        print(
            "❌ ТОЧНЫЙ АДРЕС НЕ НАЙДЕН."
        )

        print(
            "❌ Fallback на центр "
            "населённого пункта ЗАПРЕЩЁН."
        )

        return None

    # ========================================================
    # УЛИЦА БЕЗ ДОМА — FALLBACK ЗАПРЕЩЁН
    # ========================================================

    if requested_street:

        print()
        print(
            "❌ Улица указана, "
            "но подходящий результат "
            "не найден."
        )

        print(
            "❌ Центр населённого пункта "
            "для адреса с улицей использовать "
            "не будем."
        )

        return None

    # ========================================================
    # ТОЛЬКО ГОРОД — FALLBACK РАЗРЕШЁН
    # ========================================================

    if requested_locality:

        print()
        print(
            "⚠️ Номер дома не указан."
        )

        print(
            "⚠️ Улица также не указана."
        )

        print(
            "➡️ Разрешён fallback "
            "на центр населённого пункта."
        )

        return await geocode_locality_center(
            requested_locality,
            requested_region
        )

    print()
    print(
        "❌ Не удалось определить "
        "населённый пункт."
    )

    return None


# ============================================================
# OPENROUTESERVICE
# ============================================================

async def build_route(
    from_lat,
    from_lon,
    to_lat,
    to_lon
):
    if not ORS_API_KEY:

        print(
            "❌ ORS_API_KEY отсутствует."
        )

        return None

    url = (
        "https://api.openrouteservice.org/"
        "v2/directions/driving-car"
    )

    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json",
    }

    body = {
        "coordinates": [
            [
                from_lon,
                from_lat
            ],
            [
                to_lon,
                to_lat
            ]
        ],
        "units": "km",
    }

    print()
    print(
        "OPENROUTESERVICE:"
    )

    print(
        "  FROM:",
        from_lat,
        from_lon
    )

    print(
        "  TO:",
        to_lat,
        to_lon
    )

    try:

        async with aiohttp.ClientSession() as session:

            async with session.post(
                url,
                headers=headers,
                json=body,
                timeout=aiohttp.ClientTimeout(
                    total=30
                )
            ) as response:

                print(
                    "ORS HTTP:",
                    response.status
                )

                if response.status != 200:

                    body_text = await response.text()

                    print(
                        "❌ ORS RESPONSE:"
                    )

                    print(
                        body_text[:2000]
                    )

                    return None

                data = await response.json()

                routes = data.get(
                    "routes"
                )

                if not routes:

                    print(
                        "❌ ORS не вернул маршруты."
                    )

                    return None

                summary = (
                    routes[0].get(
                        "summary"
                    )
                    or {}
                )

                distance = summary.get(
                    "distance"
                )

                duration = summary.get(
                    "duration"
                )

                if distance is None:

                    print(
                        "❌ ORS не вернул "
                        "расстояние."
                    )

                    return None

                distance_km = round(
                    float(distance),
                    1
                )

                duration_minutes = None

                if duration is not None:

                    duration_minutes = round(
                        float(duration) / 60
                    )

                print(
                    "✅ ORS расстояние:",
                    distance_km,
                    "км"
                )

                if duration_minutes is not None:

                    print(
                        "✅ Время:",
                        duration_minutes,
                        "мин."
                    )

                return {
                    "distance_km": distance_km,
                    "duration_minutes": duration_minutes,
                }

    except Exception as error:

        print(
            "❌ Ошибка ORS:",
            repr(error)
        )

        return None


# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================

async def get_route_distance(
    from_address,
    to_address
):
    print()
    print("=" * 60)
    print(
        "ПОСТРОЕНИЕ МАРШРУТА"
    )
    print(
        "ОТКУДА:",
        from_address
    )
    print(
        "КУДА:",
        to_address
    )
    print("=" * 60)

    # ========================================================
    # ОТКУДА
    # ========================================================

    from_point = await geocode_exact_address(
        from_address
    )

    if not from_point:

        print()
        print(
            "❌ Не удалось определить "
            "координаты точки ОТКУДА."
        )

        print(
            "❌ МАРШРУТ НЕ БУДЕТ ПОСТРОЕН."
        )

        return None

    # ========================================================
    # КУДА
    # ========================================================

    to_point = await geocode_exact_address(
        to_address
    )

    if not to_point:

        print()
        print(
            "❌ Не удалось определить "
            "координаты точки КУДА."
        )

        print(
            "❌ МАРШРУТ НЕ БУДЕТ ПОСТРОЕН."
        )

        return None

    # ========================================================
    # МАРШРУТ
    # ========================================================

    route = await build_route(
        from_lat=from_point["lat"],
        from_lon=from_point["lon"],
        to_lat=to_point["lat"],
        to_lon=to_point["lon"]
    )

    if not route:

        print()
        print(
            "❌ Не удалось построить маршрут."
        )

        return None

    distance_km = route[
        "distance_km"
    ]

    print()
    print("=" * 60)
    print(
        "✅ МАРШРУТ ПОСТРОЕН"
    )

    print(
        "Расстояние:",
        distance_km,
        "км"
    )

    if route.get(
        "duration_minutes"
    ) is not None:

        print(
            "Время:",
            route["duration_minutes"],
            "мин."
        )

    print("=" * 60)

    return distance_km

