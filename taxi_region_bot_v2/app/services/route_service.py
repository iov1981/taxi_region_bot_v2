import os
import re
import math
from typing import Optional, Tuple, Dict, Any

import aiohttp
from dotenv import load_dotenv


# ============================================================
# ENV
# ============================================================

load_dotenv("G:/taxi_region_bot_v2/.env")

ORS_API_KEY = os.getenv("OPENROUTESERVICE_API_KEY")
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")

ORS_GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"
ORS_ROUTE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"
GEOAPIFY_URL = "https://api.geoapify.com/v1/geocode/search"


# ============================================================
# ГРАНИЦЫ ПЕНЗЕНСКОЙ ОБЛАСТИ
# ============================================================

PENZA_MIN_LON = 42.5
PENZA_MAX_LON = 47.5
PENZA_MIN_LAT = 51.8
PENZA_MAX_LAT = 55.5


# ============================================================
# ПРОВЕРЕННЫЕ ЦЕНТРЫ НАСЕЛЁННЫХ ПУНКТОВ
# ============================================================
#
# Эти координаты используются только когда нужен центр
# населённого пункта, а не конкретный дом.
#
# Особенно важно для Воробьёвки:
# Geoapify может находить одноимённый населённый пункт
# в совершенно другой точке.
#

VERIFIED_LOCALITY_COORDS = {
    # Пенза
    "пенза": (45.0067413, 53.1937836),

    # Воробьевка / Воробьёвка
    "воробьевка": (45.24727, 52.81497),
    "воробьёвка": (45.24727, 52.81497),
}


# ============================================================
# КРУПНЫЕ НАСЕЛЁННЫЕ ПУНКТЫ
# ============================================================

LARGE_LOCALITIES = {
    "пенза",
    "заречный",
    "кузнецк",
    "сердобск",
    "каменка",
    "нижний ломов",
    "никольск",
    "белинский",
    "городище",
}


# ============================================================
# НАСЕЛЁННЫЕ ПУНКТЫ
# ============================================================

CITY_LOCALITIES = {
    "пенза",
    "заречный",
    "кузнецк",
    "сердобск",
    "каменка",
    "нижний ломов",
    "никольск",
    "белинский",
    "городище",
    "бессоновка",
    "засечное",
    "чемодановка",
    "мокшан",
    "лунино",
    "шемышейка",
    "воробьевка",
    "воробьёвка",
}


# ============================================================
# СООТВЕТСТВИЯ РУССКИХ И ЛАТИНСКИХ НАЗВАНИЙ
# ============================================================

LOCALITY_ALIASES = {
    "penza": "пенза",
    "penza oblast": "пенза",

    "воробьевка": "воробьевка",
    "воробьёвка": "воробьевка",

    "vorobevka": "воробьевка",
    "vorobyovka": "воробьевка",
    "vorobyevka": "воробьевка",
    "vorobievka": "воробьевка",
}


# ============================================================
# НОРМАЛИЗАЦИЯ ТЕКСТА
# ============================================================

def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""

    value = str(value).strip().lower()

    value = value.replace("ё", "е")

    value = re.sub(r"[«»\"']", "", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


# ============================================================
# НОРМАЛИЗАЦИЯ НАЗВАНИЯ НАСЕЛЁННОГО ПУНКТА
# ============================================================

def normalize_locality_name(value: Optional[str]) -> str:
    if not value:
        return ""

    value = normalize_text(value)

    # После normalize_text:
    # ё -> е
    #
    # Поэтому Воробьёвка превращается в Воробьевка.

    aliases = {
        "penza": "пенза",
        "penza oblast": "пенза",

        "воробьевка": "воробьевка",

        "vorobevka": "воробьевка",
        "vorobyovka": "воробьевка",
        "vorobyevka": "воробьевка",
        "vorobievka": "воробьевка",
    }

    return aliases.get(value, value)


# ============================================================
# СРАВНЕНИЕ НАЗВАНИЙ НАСЕЛЁННЫХ ПУНКТОВ
# ============================================================

def locality_names_match(
    first: Optional[str],
    second: Optional[str]
) -> bool:

    first_normalized = normalize_locality_name(first)
    second_normalized = normalize_locality_name(second)

    if not first_normalized or not second_normalized:
        return False

    return first_normalized == second_normalized


# ============================================================
# ПРОВЕРКА КООРДИНАТ
# ============================================================

def is_inside_penza_region(
    longitude: float,
    latitude: float
) -> bool:

    return (
        PENZA_MIN_LON <= longitude <= PENZA_MAX_LON
        and
        PENZA_MIN_LAT <= latitude <= PENZA_MAX_LAT
    )


# ============================================================
# НОМЕР ДОМА
# ============================================================

def has_house_number(address: Optional[str]) -> bool:
    if not address:
        return False

    text = normalize_text(address)

    return bool(
        re.search(
            r"(?:дом|д\.?|№)?\s*"
            r"\d+[а-яa-z]?"
            r"(?:[\/\-]\d+[а-яa-z]?)?",
            text
        )
    )


def extract_house_number(
    address: Optional[str]
) -> Optional[str]:

    if not address:
        return None

    text = normalize_text(address)

    match = re.search(
        r"(?:дом|д\.?|№)?\s*"
        r"(\d+[а-яa-z]?"
        r"(?:[\/\-]\d+[а-яa-z]?)?)",
        text
    )

    if match:
        return match.group(1)

    return None


# ============================================================
# НАЗВАНИЕ УЛИЦЫ
# ============================================================

def extract_street_name(
    address: Optional[str]
) -> Optional[str]:

    if not address:
        return None

    text = normalize_text(address)

    text = re.sub(
        r"\b(?:дом|д\.?)\s*"
        r"\d+[а-яa-z]?"
        r"(?:[\/\-]\d+[а-яa-z]?)?",
        "",
        text
    )

    text = re.sub(
        r"\b\d+[а-яa-z]?"
        r"(?:[\/\-]\d+[а-яa-z]?)?\b",
        "",
        text
    )

    # Убираем название населённого пункта
    locality = extract_requested_locality(text)

    if locality:
        text = re.sub(
            re.escape(locality),
            "",
            text,
            flags=re.IGNORECASE
        )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    text = text.strip(" ,.-")

    return text or None


# ============================================================
# ОПРЕДЕЛЕНИЕ НАСЕЛЁННОГО ПУНКТА
# ============================================================

def extract_requested_locality(
    address: Optional[str]
) -> Optional[str]:

    if not address:
        return None

    text = normalize_text(address)

    # Сначала длинные названия
    known_localities = sorted(
        CITY_LOCALITIES,
        key=len,
        reverse=True
    )

    for locality in known_localities:

        if locality in text:

            return normalize_locality_name(
                locality
            )

    # Дополнительная проверка латиницы
    for alias, canonical in LOCALITY_ALIASES.items():

        if alias in text:

            return canonical

    return None


# ============================================================
# ТИП НАСЕЛЁННОГО ПУНКТА
# ============================================================

def get_locality_type(
    locality: Optional[str]
) -> str:

    locality = normalize_locality_name(
        locality
    )

    if not locality:
        return "unknown"

    if locality in LARGE_LOCALITIES:
        return "large"

    if locality in CITY_LOCALITIES:
        return "small"

    return "unknown"


def can_use_locality_fallback(
    locality: Optional[str]
) -> bool:

    locality = normalize_locality_name(
        locality
    )

    if not locality:
        return False

    return locality in CITY_LOCALITIES


# ============================================================
# GEOAPIFY FEATURE
# ============================================================

def get_feature_layer(
    feature: Dict[str, Any]
) -> Dict[str, Any]:

    return feature.get("properties") or {}


# ============================================================
# ПРОВЕРКА НАСЕЛЁННОГО ПУНКТА
# ============================================================

def feature_belongs_to_locality(
    feature: Dict[str, Any],
    requested_locality: str
) -> bool:

    properties = get_feature_layer(
        feature
    )

    requested = normalize_locality_name(
        requested_locality
    )

    fields = [
        properties.get("city"),
        properties.get("town"),
        properties.get("village"),
        properties.get("locality"),
    ]

    for value in fields:

        if locality_names_match(
            value,
            requested
        ):
            return True

    return False


# ============================================================
# ОЦЕНКА GEOAPIFY
# ============================================================

def score_feature(
    feature: Dict[str, Any],
    requested_locality: str,
    requested_address: Optional[str] = None
) -> int:

    properties = get_feature_layer(
        feature
    )

    requested = normalize_locality_name(
        requested_locality
    )

    score = 0

    name = properties.get("name")
    city = properties.get("city")
    town = properties.get("town")
    village = properties.get("village")
    locality = properties.get("locality")
    municipality = properties.get("municipality")

    # --------------------------------------------------------
    # НАЗВАНИЕ
    # --------------------------------------------------------

    if locality_names_match(
        name,
        requested
    ):
        score += 100

    # --------------------------------------------------------
    # СТРУКТУРНЫЕ ПОЛЯ
    # --------------------------------------------------------

    if locality_names_match(
        city,
        requested
    ):
        score += 100

    if locality_names_match(
        town,
        requested
    ):
        score += 100

    if locality_names_match(
        village,
        requested
    ):
        score += 100

    if locality_names_match(
        locality,
        requested
    ):
        score += 100

    # municipality НЕ используем как подтверждение
    # населённого пункта.

    # --------------------------------------------------------
    # ОБЛАСТЬ
    # --------------------------------------------------------

    state = normalize_text(
        properties.get("state")
        or ""
    )

    formatted = normalize_text(
        properties.get("formatted")
        or ""
    )

    if (
        "пензенская область" in state
        or
        "penza oblast" in state
        or
        "пензенская область" in formatted
        or
        "penza oblast" in formatted
    ):
        score += 50

    # --------------------------------------------------------
    # ТОЧНЫЙ АДРЕС
    # --------------------------------------------------------

    if requested_address:

        requested_house = extract_house_number(
            requested_address
        )

        candidate_house = (
            properties.get("housenumber")
            or properties.get("house_number")
            or properties.get("street_number")
        )

        if (
            requested_house
            and
            candidate_house
            and
            normalize_text(
                str(requested_house)
            )
            ==
            normalize_text(
                str(candidate_house)
            )
        ):
            score += 300

        requested_street = extract_street_name(
            requested_address
        )

        candidate_street = (
            properties.get("street")
            or properties.get("street_name")
        )

        if (
            requested_street
            and
            candidate_street
        ):

            requested_street_normalized = (
                normalize_text(
                    requested_street
                )
            )

            candidate_street_normalized = (
                normalize_text(
                    candidate_street
                )
            )

            if (
                requested_street_normalized
                in candidate_street_normalized
                or
                candidate_street_normalized
                in requested_street_normalized
            ):
                score += 200

    return score


# ============================================================
# СТРОГАЯ ПРОВЕРКА ТОЧНОГО АДРЕСА
# ============================================================

def address_matches_request(
    feature: Dict[str, Any],
    requested_address: str,
    requested_locality: Optional[str]
) -> bool:

    properties = get_feature_layer(
        feature
    )

    # --------------------------------------------------------
    # НАСЕЛЁННЫЙ ПУНКТ
    # --------------------------------------------------------

    if requested_locality:

        if not feature_belongs_to_locality(
            feature,
            requested_locality
        ):
            print(
                "  ❌ Населённый пункт "
                "не совпадает."
            )

            return False

    # --------------------------------------------------------
    # НОМЕР ДОМА
    # --------------------------------------------------------

    requested_house = extract_house_number(
        requested_address
    )

    if requested_house:

        candidate_house = (
            properties.get("housenumber")
            or properties.get("house_number")
            or properties.get("street_number")
        )

        if not candidate_house:

            print(
                "  ❌ В кандидате нет номера дома."
            )

            return False

        if normalize_text(
            str(candidate_house)
        ) != normalize_text(
            str(requested_house)
        ):

            print(
                "  ❌ Номер дома не совпадает:"
            )

            print(
                "     нужен:",
                requested_house
            )

            print(
                "     найден:",
                candidate_house
            )

            return False

    # --------------------------------------------------------
    # УЛИЦА
    # --------------------------------------------------------

    requested_street = extract_street_name(
        requested_address
    )

    if requested_street:

        candidate_street = (
            properties.get("street")
            or properties.get("street_name")
        )

        if not candidate_street:

            print(
                "  ❌ В кандидате нет улицы."
            )

            return False

        requested_street_normalized = (
            normalize_text(
                requested_street
            )
        )

        candidate_street_normalized = (
            normalize_text(
                candidate_street
            )
        )

        if (
            requested_street_normalized
            not in candidate_street_normalized
            and
            candidate_street_normalized
            not in requested_street_normalized
        ):

            print(
                "  ❌ Улица не совпадает:"
            )

            print(
                "     нужна:",
                requested_street
            )

            print(
                "     найдена:",
                candidate_street
            )

            return False

    return True


# ============================================================
# ВОЗДУШНОЕ РАССТОЯНИЕ
# ============================================================

def calculate_air_distance_km(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float
) -> float:

    radius = 6371.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    d_phi = math.radians(
        lat2 - lat1
    )

    d_lambda = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(d_phi / 2) ** 2
        +
        math.cos(phi1)
        * math.cos(phi2)
        * math.sin(d_lambda / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return radius * c


# ============================================================
# PATTERN
# ============================================================

def get_place_pattern(
    locality: str
) -> str:

    locality = normalize_locality_name(
        locality
    )

    if locality in LARGE_LOCALITIES:
        return "city"

    return "locality"


# ============================================================
# GEOAPIFY — ТОЧНЫЙ АДРЕС
# ============================================================

async def geocode_address_geoapify(
    address: str,
    requested_locality: Optional[str] = None
) -> Optional[Tuple[float, float]]:

    if not GEOAPIFY_API_KEY:

        print(
            "GEOAPIFY_API_KEY не найден."
        )

        return None

    print()
    print(
        "GEOAPIFY: поиск точного адреса"
    )

    print(
        "  запрос:",
        address
    )

    params = {
        "text": address,
        "apiKey": GEOAPIFY_API_KEY,
        "limit": 10,
        "filter": (
            f"rect:"
            f"{PENZA_MIN_LON},"
            f"{PENZA_MIN_LAT},"
            f"{PENZA_MAX_LON},"
            f"{PENZA_MAX_LAT}"
        ),
    }

    try:

        async with aiohttp.ClientSession() as session:

            async with session.get(
                GEOAPIFY_URL,
                params=params,
                timeout=20
            ) as response:

                print(
                    "  HTTP:",
                    response.status
                )

                if response.status != 200:

                    text = await response.text()

                    print(
                        "  ❌ GEOAPIFY HTTP error:",
                        text[:500]
                    )

                    return None

                data = await response.json()

    except Exception as error:

        print(
            "  ❌ Ошибка GEOAPIFY:",
            repr(error)
        )

        return None

    features = data.get(
        "features"
    ) or []

    if not features:

        print(
            "  ❌ GEOAPIFY не вернул "
            "кандидатов."
        )

        return None

    best_feature = None
    best_score = -100000

    for index, feature in enumerate(
        features,
        start=1
    ):

        properties = get_feature_layer(
            feature
        )

        geometry = feature.get(
            "geometry"
        ) or {}

        coordinates = geometry.get(
            "coordinates"
        )

        if (
            not coordinates
            or
            len(coordinates) < 2
        ):
            continue

        lon = float(
            coordinates[0]
        )

        lat = float(
            coordinates[1]
        )

        if not is_inside_penza_region(
            lon,
            lat
        ):
            continue

        score = score_feature(
            feature,
            requested_locality or "",
            address
        )

        print()
        print(
            f"  КАНДИДАТ GEOAPIFY #{index}"
        )

        print(
            "    name:",
            properties.get("name")
        )

        print(
            "    formatted:",
            properties.get("formatted")
        )

        print(
            "    city:",
            properties.get("city")
        )

        print(
            "    town:",
            properties.get("town")
        )

        print(
            "    village:",
            properties.get("village")
        )

        print(
            "    locality:",
            properties.get("locality")
        )

        print(
            "    street:",
            properties.get("street")
        )

        print(
            "    housenumber:",
            properties.get("housenumber")
        )

        print(
            "    SCORE:",
            score
        )

        if score > best_score:

            best_score = score
            best_feature = feature

    if not best_feature:

        print(
            "  ❌ Подходящий адрес "
            "не найден."
        )

        return None

    # --------------------------------------------------------
    # СТРОГАЯ ПРОВЕРКА
    # --------------------------------------------------------

    if not address_matches_request(
        best_feature,
        address,
        requested_locality
    ):

        print()
        print(
            "  ❌ Лучший кандидат "
            "НЕ прошёл строгую "
            "проверку адреса."
        )

        return None

    coordinates = (
        best_feature
        .get("geometry", {})
        .get("coordinates")
    )

    if not coordinates:
        return None

    lon = float(
        coordinates[0]
    )

    lat = float(
        coordinates[1]
    )

    print()
    print(
        "GEOAPIFY: точный адрес "
        "подтверждён:"
    )

    print(
        " ",
        (lon, lat)
    )

    return lon, lat


# ============================================================
# ORS — ЦЕНТР НАСЕЛЁННОГО ПУНКТА
# ============================================================

async def geocode_locality_ors(
    locality: str
) -> Optional[Tuple[float, float]]:

    if not ORS_API_KEY:

        print(
            "ORS_API_KEY не найден."
        )

        return None

    locality = normalize_locality_name(
        locality
    )

    query = (
        f"{locality}, "
        f"Пензенская область, Россия"
    )

    print()
    print(
        "ORS: поиск центра "
        "населённого пункта"
    )

    print(
        "  запрос:",
        query
    )

    params = {
        "api_key": ORS_API_KEY,
        "text": query,
        "size": 10,
        "boundary.country": "RUS",
    }

    try:

        async with aiohttp.ClientSession() as session:

            async with session.get(
                ORS_GEOCODE_URL,
                params=params,
                timeout=20
            ) as response:

                print(
                    "  HTTP:",
                    response.status
                )

                if response.status != 200:

                    text = await response.text()

                    print(
                        "  ❌ ORS HTTP error:",
                        text[:500]
                    )

                    return None

                data = await response.json()

    except Exception as error:

        print(
            "  ❌ Ошибка ORS:",
            repr(error)
        )

        return None

    features = data.get(
        "features"
    ) or []

    for feature in features:

        properties = feature.get(
            "properties"
        ) or {}

        geometry = feature.get(
            "geometry"
        ) or {}

        coordinates = geometry.get(
            "coordinates"
        )

        if (
            not coordinates
            or
            len(coordinates) < 2
        ):
            continue

        lon = float(
            coordinates[0]
        )

        lat = float(
            coordinates[1]
        )

        if not is_inside_penza_region(
            lon,
            lat
        ):
            continue

        label = normalize_text(
            properties.get("label")
            or properties.get("name")
            or ""
        )

        if (
            locality not in label
            and
            locality not in normalize_locality_name(
                properties.get("name")
            )
        ):
            continue

        print(
            "ORS: центр найден:",
            (lon, lat)
        )

        return lon, lat

    print(
        "ORS: подходящий населённый "
        "пункт не найден."
    )

    return None


# ============================================================
# GEOAPIFY — ЦЕНТР НАСЕЛЁННОГО ПУНКТА
# ============================================================

async def geocode_locality_geoapify(
    locality: str
) -> Optional[Tuple[float, float]]:

    if not GEOAPIFY_API_KEY:

        print(
            "GEOAPIFY_API_KEY не найден."
        )

        return None

    locality = normalize_locality_name(
        locality
    )

    # --------------------------------------------------------
    # Для известных проблемных населённых пунктов
    # проверенный центр должен иметь приоритет.
    # --------------------------------------------------------

    if locality in VERIFIED_LOCALITY_COORDS:

        coordinates = (
            VERIFIED_LOCALITY_COORDS[
                locality
            ]
        )

        print()
        print(
            "GEOAPIFY: используется "
            "проверенный центр:"
        )

        print(
            " ",
            coordinates
        )

        return coordinates

    query = (
        f"{locality}, "
        f"Пензенская область, Россия"
    )

    print()
    print(
        "GEOAPIFY: поиск центра "
        "населённого пункта"
    )

    print(
        "  запрос:",
        query
    )

    params = {
        "text": query,
        "apiKey": GEOAPIFY_API_KEY,
        "limit": 10,
        "filter": (
            f"rect:"
            f"{PENZA_MIN_LON},"
            f"{PENZA_MIN_LAT},"
            f"{PENZA_MAX_LON},"
            f"{PENZA_MAX_LAT}"
        ),
    }

    try:

        async with aiohttp.ClientSession() as session:

            async with session.get(
                GEOAPIFY_URL,
                params=params,
                timeout=20
            ) as response:

                print(
                    "  HTTP:",
                    response.status
                )

                if response.status != 200:

                    text = await response.text()

                    print(
                        "  ❌ GEOAPIFY HTTP error:",
                        text[:500]
                    )

                    return None

                data = await response.json()

    except Exception as error:

        print(
            "  ❌ Ошибка GEOAPIFY:",
            repr(error)
        )

        return None

    features = data.get(
        "features"
    ) or []

    best_feature = None
    best_score = -100000

    for index, feature in enumerate(
        features,
        start=1
    ):

        properties = get_feature_layer(
            feature
        )

        geometry = feature.get(
            "geometry"
        ) or {}

        coordinates = geometry.get(
            "coordinates"
        )

        if (
            not coordinates
            or
            len(coordinates) < 2
        ):
            continue

        lon = float(
            coordinates[0]
        )

        lat = float(
            coordinates[1]
        )

        if not is_inside_penza_region(
            lon,
            lat
        ):
            continue

        score = score_feature(
            feature,
            locality
        )

        print()
        print(
            f"  КАНДИДАТ GEOAPIFY #{index}"
        )

        print(
            "    name:",
            properties.get("name")
        )

        print(
            "    formatted:",
            properties.get("formatted")
        )

        print(
            "    city:",
            properties.get("city")
        )

        print(
            "    town:",
            properties.get("town")
        )

        print(
            "    village:",
            properties.get("village")
        )

        print(
            "    locality:",
            properties.get("locality")
        )

        print(
            "    municipality:",
            properties.get("municipality")
        )

        print(
            "    SCORE:",
            score
        )

        if score > best_score:

            best_score = score
            best_feature = feature

    if not best_feature:

        print(
            "GEOAPIFY: подходящий центр "
            "не найден."
        )

        return None

    coordinates = (
        best_feature
        .get("geometry", {})
        .get("coordinates")
    )

    if not coordinates:
        return None

    lon = float(
        coordinates[0]
    )

    lat = float(
        coordinates[1]
    )

    print()
    print(
        "GEOAPIFY: центр найден:",
        (lon, lat)
    )

    print(
        "  SCORE:",
        best_score
    )

    return lon, lat


# ============================================================
# FALLBACK
# ============================================================

async def fallback_to_locality(
    locality: str
) -> Optional[Tuple[float, float]]:

    locality = normalize_locality_name(
        locality
    )

    # --------------------------------------------------------
    # ПРОВЕРЕННЫЕ КООРДИНАТЫ
    # --------------------------------------------------------

    if locality in VERIFIED_LOCALITY_COORDS:

        coordinates = (
            VERIFIED_LOCALITY_COORDS[
                locality
            ]
        )

        print()
        print(
            "ИСПОЛЬЗУЕМ ПРОВЕРЕННЫЙ "
            "ЦЕНТР:"
        )

        print(
            "  населённый пункт:",
            locality
        )

        print(
            "  координаты:",
            coordinates
        )

        return coordinates

    # --------------------------------------------------------
    # ORS
    # --------------------------------------------------------

    coordinates = await geocode_locality_ors(
        locality
    )

    if coordinates:
        return coordinates

    # --------------------------------------------------------
    # GEOAPIFY
    # --------------------------------------------------------

    coordinates = await geocode_locality_geoapify(
        locality
    )

    if coordinates:
        return coordinates

    return None


# ============================================================
# ОСНОВНОЕ ГЕОКОДИРОВАНИЕ
# ============================================================

async def geocode(
    address: str
) -> Optional[Tuple[float, float]]:

    print()
    print("=" * 60)
    print(
        "ГЕОКОДИРОВАНИЕ:",
        address
    )
    print("=" * 60)

    locality = extract_requested_locality(
        address
    )

    print(
        "НАСЕЛЁННЫЙ ПУНКТ:",
        locality
    )

    if not locality:

        print(
            "❌ Не удалось определить "
            "населённый пункт."
        )

        return None

    locality = normalize_locality_name(
        locality
    )

    # ========================================================
    # НОМЕР ДОМА ЕСТЬ
    # ========================================================

    if has_house_number(address):

        print()
        print(
            "ЕСТЬ НОМЕР ДОМА."
        )

        # ----------------------------------------------------
        # Сначала ищем конкретный адрес.
        # ----------------------------------------------------

        coordinates = await geocode_address_geoapify(
            address,
            locality
        )

        if coordinates:

            return coordinates

        print()
        print(
            "❌ Точный адрес не подтверждён."
        )

        # ----------------------------------------------------
        # Для небольшого населённого пункта
        # можно перейти на центр.
        # ----------------------------------------------------

        if can_use_locality_fallback(
            locality
        ):

            print(
                "Разрешён fallback "
                "на центр населённого пункта."
            )

            return await fallback_to_locality(
                locality
            )

        # ----------------------------------------------------
        # Для Пензы, Заречного и других крупных
        # населённых пунктов НЕ подменяем дом центром.
        # ----------------------------------------------------

        print(
            "❌ Для крупного населённого "
            "пункта центр вместо указанного "
            "дома НЕ используется."
        )

        return None

    # ========================================================
    # НОМЕРА ДОМА НЕТ
    # ========================================================

    print()
    print(
        "ТОЧНОГО НОМЕРА ДОМА НЕТ."
    )

    print(
        "Ищем населённый пункт."
    )

    return await fallback_to_locality(
        locality
    )


# ============================================================
# ИЗВЛЕЧЕНИЕ РАССТОЯНИЯ ИЗ ORS
# ============================================================

def extract_ors_distance(
    data: Dict[str, Any]
) -> Optional[float]:

    # ========================================================
    # ВАРИАНТ 1:
    #
    # FeatureCollection
    #
    # features[0]
    #   properties
    #     summary
    #       distance
    #
    # ========================================================

    features = data.get(
        "features"
    )

    if features:

        try:

            feature = features[0]

            properties = (
                feature.get("properties")
                or {}
            )

            summary = (
                properties.get("summary")
                or {}
            )

            distance = summary.get(
                "distance"
            )

            if distance is not None:

                print(
                    "ORS FORMAT: FeatureCollection"
                )

                return float(
                    distance
                )

        except Exception as error:

            print(
                "Ошибка разбора "
                "ORS features:",
                repr(error)
            )

    # ========================================================
    # ВАРИАНТ 2:
    #
    # routes[0]
    #   summary
    #     distance
    #
    # ========================================================

    routes = data.get(
        "routes"
    )

    if routes:

        try:

            route = routes[0]

            summary = (
                route.get("summary")
                or {}
            )

            distance = summary.get(
                "distance"
            )

            if distance is not None:

                print(
                    "ORS FORMAT: routes"
                )

                return float(
                    distance
                )

        except Exception as error:

            print(
                "Ошибка разбора "
                "ORS routes:",
                repr(error)
            )

    return None


# ============================================================
# ПОЛУЧЕНИЕ ДЛИТЕЛЬНОСТИ ORS
# ============================================================

def extract_ors_duration(
    data: Dict[str, Any]
) -> Optional[float]:

    features = data.get(
        "features"
    )

    if features:

        try:

            duration = (
                features[0]
                .get("properties", {})
                .get("summary", {})
                .get("duration")
            )

            if duration is not None:
                return float(duration)

        except Exception:
            pass

    routes = data.get(
        "routes"
    )

    if routes:

        try:

            duration = (
                routes[0]
                .get("summary", {})
                .get("duration")
            )

            if duration is not None:
                return float(duration)

        except Exception:
            pass

    return None


# ============================================================
# ПОСТРОЕНИЕ МАРШРУТА
# ============================================================

async def get_route_distance(
    from_address: str,
    to_address: str
) -> Optional[float]:

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

    from_coordinates = await geocode(
        from_address
    )

    if not from_coordinates:

        print(
            "❌ Не удалось определить "
            "координаты ОТКУДА."
        )

        return None

    print()
    print(
        "КООРДИНАТЫ ОТКУДА:",
        from_coordinates
    )

    # ========================================================
    # КУДА
    # ========================================================

    to_coordinates = await geocode(
        to_address
    )

    if not to_coordinates:

        print(
            "❌ Не удалось определить "
            "координаты КУДА."
        )

        return None

    print()
    print(
        "КООРДИНАТЫ КУДА:",
        to_coordinates
    )

    # ========================================================
    # ORS API KEY
    # ========================================================

    if not ORS_API_KEY:

        print(
            "❌ OPENROUTESERVICE_API_KEY "
            "не найден."
        )

        return None

    # ========================================================
    # КООРДИНАТЫ ORS
    # ========================================================

    coordinates = [
        [
            from_coordinates[0],
            from_coordinates[1]
        ],
        [
            to_coordinates[0],
            to_coordinates[1]
        ]
    ]

    print()
    print(
        "ОТПРАВКА ЗАПРОСА В ORS..."
    )

    payload = {
        "coordinates": coordinates,
        "instructions": True,
        "units": "km",
    }

    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json",
    }

    # ========================================================
    # ЗАПРОС
    # ========================================================

    try:

        async with aiohttp.ClientSession() as session:

            async with session.post(
                ORS_ROUTE_URL,
                json=payload,
                headers=headers,
                timeout=30
            ) as response:

                print(
                    "ORS ROUTE HTTP:",
                    response.status
                )

                if response.status != 200:

                    text = await response.text()

                    print(
                        "❌ ORS ROUTE ERROR:"
                    )

                    print(
                        text[:1000]
                    )

                    return None

                data = await response.json()

    except Exception as error:

        print(
            "❌ Ошибка запроса маршрута ORS:",
            repr(error)
        )

        return None

    # ========================================================
    # РАССТОЯНИЕ
    # ========================================================

    distance = extract_ors_distance(
        data
    )

    if distance is None:

        print(
            "❌ ORS не вернул "
            "расстояние."
        )

        print(
            "Ключи ответа:",
            list(data.keys())
        )

        return None

    # ========================================================
    # ORS МОЖЕТ ВЕРНУТЬ КМ
    #
    # В нашем текущем ответе:
    #
    # distance = 52.6
    #
    # units = km
    #
    # Поэтому здесь НЕ делим на 1000.
    # ========================================================

    distance_km = round(
        float(distance),
        1
    )

    # ========================================================
    # ДЛИТЕЛЬНОСТЬ
    # ========================================================

    duration = extract_ors_duration(
        data
    )

    print()
    print(
        "✅ МАРШРУТ ПОСТРОЕН"
    )

    print(
        "РАССТОЯНИЕ:",
        distance_km,
        "км"
    )

    if duration is not None:

        duration_minutes = round(
            duration / 60
        )

        print(
            "ВРЕМЯ В ПУТИ:",
            duration_minutes,
            "мин."
        )

    print()

    return distance_km