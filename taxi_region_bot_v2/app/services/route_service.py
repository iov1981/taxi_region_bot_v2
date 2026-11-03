import os
import re
import aiohttp

from dotenv import load_dotenv

load_dotenv()

# ============================================================
# НАСТРОЙКИ РЕГИОНА
# ============================================================

DEFAULT_CITY = "Пенза"
DEFAULT_REGION = "Пензенская область"
DEFAULT_COUNTRY = "Россия"

# Центр Пензы (lat, lon)
DEFAULT_CENTER_LAT = 53.1959
DEFAULT_CENTER_LON = 45.0183

# Границы Пензенской области (lon_min, lat_min, lon_max, lat_max)
PENZA_BBOX = "41.7,52.5,47.2,54.0"

ORS_API_KEY = os.getenv("ORS_API_KEY")
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")

MAX_ALLOWED_HOUSE_NUMBER = 999

print()
print("=" * 60)
print("ROUTE SERVICE V2.9 (SPUTNIK & DISTRICTS SUPPORT)")
print("ORS_API_KEY:", "OK" if ORS_API_KEY else "НЕТ")
print("GEOAPIFY_API_KEY:", "OK" if GEOAPIFY_API_KEY else "НЕТ")
print("DEFAULT CITY:", DEFAULT_CITY)
print("=" * 60)


# ============================================================
# ОБЩИЕ ФУНКЦИИ
# ============================================================

def normalize_text(value):
    if value is None:
        return ""
    value = str(value).strip().lower()
    value = value.replace("ё", "е")
    return re.sub(r"\s+", " ", value)


def normalize_poi_and_landmarks(address: str) -> str:
    """Распознавание популярных ориентиров Пензы и районов."""
    norm = normalize_text(address)

    # Вокзалы и аэропорт
    if re.search(r"\b(?:вокзал|вокзала|жд\s*вокзал|пенза\s*1)\b", norm):
        return f"{DEFAULT_CITY}, Привокзальная площадь, 1"

    if re.search(r"\b(?:автовокзал|автовокзала)\b", norm):
        return f"{DEFAULT_CITY}, ул. Луначарского, 1"

    if re.search(r"\b(?:аэропорт|аэропорта)\b", norm):
        return f"{DEFAULT_CITY}, Центральная ул., 2"

    return address


def normalize_street_name(value):
    value = normalize_text(value)

    # Убираем упоминание микрорайонов из улицы
    value = re.sub(r"\b(?:город\s+спутник|спутник|заря|терновка|арбеково|гпз)\b", " ", value)

    # Типы улиц
    value = re.sub(r"\b(?:улица|ул)\.?\b", " ", value)
    value = re.sub(r"\b(?:проспект|просп|пр-т)\.?\b", " ", value)
    value = re.sub(r"\b(?:переулок|пер)\.?\b", " ", value)
    value = re.sub(r"\b(?:шоссе|ш)\.?\b", " ", value)
    value = re.sub(r"\b(?:площадь|пл)\.?\b", " ", value)
    value = re.sub(r"\b(?:бульвар|бул)\.?\b", " ", value)
    value = re.sub(r"\b(?:набережная|наб)\.?\b", " ", value)
    value = re.sub(r"\b(?:проезд|пр-д)\.?\b", " ", value)
    value = re.sub(r"[,\.;:]", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_house_number(value):
    if value is None:
        return ""
    value = str(value).strip().lower()
    value = re.sub(r"\s+", "", value)
    value = value.replace("корпус", "к").replace("корп.", "к").replace("корп", "к")
    value = value.replace("строение", "стр").replace("ст.", "стр")
    return value


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


def extract_house_number(address):
    if not address:
        return None
    pattern = get_house_pattern()
    match = re.search(rf"(?<!\d)({pattern})(?!\d)", str(address), flags=re.IGNORECASE)
    if not match:
        return None
    return normalize_house_number(match.group(1))


def extract_street_name(address):
    if not address:
        return None

    text = str(address).strip()
    house = extract_house_number(text)

    if house:
        pattern = get_house_pattern()
        text_without_house = re.sub(rf"(?<!\d){pattern}(?!\d)", "", text, count=1, flags=re.IGNORECASE)
    else:
        text_without_house = text

    text_without_house = re.sub(r"\s+", " ", text_without_house).strip(" ,;.")
    if not text_without_house:
        return None

    known_places = {
        "пенза", "заречный", "кузнецк", "сердобск", "каменка",
        "нижний ломов", "никольск", "белинский", "городище",
        "саратов", "саранск", "энгельс", "засечное"
    }

    parts = [p.strip() for p in re.split(r",", text_without_house) if p.strip()]

    if len(parts) >= 2:
        for part in reversed(parts):
            if normalize_text(part) in known_places:
                continue
            street = normalize_street_name(part)
            if street:
                return street
        return None

    only_part = normalize_text(parts[0] if parts else text_without_house)
    for place in sorted(known_places, key=len, reverse=True):
        only_part = re.sub(r"^" + re.escape(place) + r"(?:\s+|,\s*)", "", only_part, flags=re.IGNORECASE)

    street = normalize_street_name(only_part)
    return street if street else None


def streets_match(requested_street, found_street):
    requested = normalize_street_name(requested_street)
    found = normalize_street_name(found_street)
    if not requested or not found:
        return False
    return requested == found or requested in found or found in requested


# ============================================================
# ОПРЕДЕЛЕНИЕ НАСЕЛЁННОГО ПУНКТА И МИКРОРАЙОНА
# ============================================================

def extract_locality_from_address(address):
    if not address:
        return DEFAULT_CITY

    text = normalize_text(address)

    # Проверка на Город Спутник (Засечное)
    if "спутник" in text or "засечное" in text:
        return "Засечное"

    known_places = (
        "пенза", "заречный", "кузнецк", "сердобск", "каменка",
        "нижний ломов", "никольск", "белинский", "городище",
        "воробьевка", "воробьевку", "воробьёвка", "воробьёвку",
        "саратов", "саранск"
    )

    for place in sorted(known_places, key=len, reverse=True):
        if place in text:
            if "воробьев" in place or "воробьёв" in place:
                return "воробьевка"
            return place

    return DEFAULT_CITY


def detect_region(address):
    text = normalize_text(address)
    if "саратов" in text:
        return "Саратовская область"
    if "саранск" in text or "мордови" in text:
        return "Республика Мордовия"
    return DEFAULT_REGION


# ============================================================
# GEOAPIFY
# ============================================================

async def geoapify_request(text, bias_lat=DEFAULT_CENTER_LAT, bias_lon=DEFAULT_CENTER_LON):
    if not GEOAPIFY_API_KEY:
        print("❌ GEOAPIFY_API_KEY отсутствует")
        return []

    url = "https://api.geoapify.com/v1/geocode/search"

    params = {
        "text": text,
        "apiKey": GEOAPIFY_API_KEY,
        "limit": 5,
        "lang": "ru",
        "filter": f"rect:{PENZA_BBOX}",
        "bias": f"proximity:{bias_lon},{bias_lat}"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as response:
                if response.status != 200:
                    return []
                data = await response.json()
                return data.get("features", [])
    except Exception as error:
        print("❌ Ошибка запроса Geoapify:", repr(error))
        return []


def get_found_house(properties):
    if not properties:
        return None
    house = (
        properties.get("housenumber")
        or properties.get("house_number")
        or properties.get("street_number")
    )
    return normalize_house_number(house) if house is not None else None


def get_found_street(properties):
    if not properties:
        return None
    return (
        properties.get("street")
        or properties.get("street_name")
        or properties.get("name")
    )


def exact_address_match(properties, requested_street, requested_house):
    if not properties:
        return False

    found_house = get_found_house(properties)
    found_street = get_found_street(properties)
    result_type = normalize_text(properties.get("result_type") or properties.get("type") or "")

    if requested_house:
        if not found_house:
            return False
        if normalize_house_number(requested_house) != normalize_house_number(found_house):
            return False

    if requested_street:
        if not found_street:
            return False
        if not streets_match(requested_street, found_street):
            return False

    if result_type in ("building", "amenity"):
        return True

    if requested_house and found_house and requested_street and found_street:
        return True

    if requested_street:
        return True

    return True


# ============================================================
# ТОЧНОЕ ГЕОКОДИРОВАНИЕ
# ============================================================

async def geocode_exact_address(raw_address):
    if not raw_address:
        return None

    address = normalize_poi_and_landmarks(raw_address)
    norm_address = normalize_text(address)

    is_sputnik = "спутник" in norm_address or "засечное" in norm_address

    requested_locality = extract_locality_from_address(address)
    requested_region = detect_region(address)
    requested_house = extract_house_number(address)
    requested_street = extract_street_name(address)

    print()
    print("=" * 60)
    print(f"ГЕОКОДИРОВАНИЕ: {address}")
    print(f"Город/НП: {requested_locality} | Улица: {requested_street} | Дом: {requested_house}")
    print("=" * 60)

    queries = []

    # Специальная логика для Города Спутника (Засечное)
    if is_sputnik and requested_street and requested_house:
        queries.append(f"Засечное, Спутник, {requested_street}, {requested_house}, Пензенская область")
        queries.append(f"с. Засечное, {requested_street}, {requested_house}")
        queries.append(f"Спутник, {requested_street}, {requested_house}")

    # Обычный приоритетный поиск: Улица + Дом + Город
    if requested_street and requested_house:
        queries.append(f"{requested_locality}, {requested_street}, {requested_house}, {requested_region}")

    # Резервные варианты
    queries.append(f"{requested_locality}, {address}")
    queries.append(str(address).strip())

    unique_queries = []
    for q in queries:
        if q and q.lower() not in [u.lower() for u in unique_queries]:
            unique_queries.append(q)

    for index, query in enumerate(unique_queries, start=1):
        print(f"Geoapify запрос #{index}: {query}")
        features = await geoapify_request(query)

        for feature in features:
            properties = feature.get("properties") or {}
            geometry = feature.get("geometry") or {}
            coordinates = geometry.get("coordinates")

            if not coordinates or len(coordinates) < 2:
                continue

            # Если мы искали в Спутнике, проверяем, чтобы результат не улетел в Зарю
            formatted = normalize_text(properties.get("formatted", ""))
            if is_sputnik and ("заря" in formatted and "засечное" not in formatted and "спутник" not in formatted):
                print(f"  ⚠️ Пропущен дубль из Зари: {properties.get('formatted')}")
                continue

            matched = exact_address_match(
                properties=properties,
                requested_street=requested_street,
                requested_house=requested_house
            )

            if matched:
                lon, lat = coordinates[0], coordinates[1]
                print(f"  ✅ Точка найдена: {properties.get('formatted')} -> ({lat}, {lon})")
                return {
                    "lat": lat,
                    "lon": lon,
                    "formatted": properties.get("formatted"),
                    "properties": properties,
                }

    if not requested_house:
        print("⚠️ Точный дом не указан, берём центр населённого пункта...")
        features = await geoapify_request(f"{requested_locality}, {requested_region}")
        if features and features[0].get("geometry", {}).get("coordinates"):
            coords = features[0]["geometry"]["coordinates"]
            return {"lat": coords[1], "lon": coords[0], "formatted": requested_locality}

    print("❌ Не удалось найти координаты для адреса.")
    return None


# ============================================================
# OPENROUTESERVICE
# ============================================================

async def build_route(from_lat, from_lon, to_lat, to_lon):
    if not ORS_API_KEY:
        print("❌ ORS_API_KEY отсутствует.")
        return None

    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json",
    }
    body = {
        "coordinates": [
            [from_lon, from_lat],
            [to_lon, to_lat]
        ],
        "units": "km",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    body_text = await response.text()
                    print("❌ Ошибка ответа ORS:", body_text[:500])
                    return None

                data = await response.json()
                routes = data.get("routes")
                if not routes:
                    return None

                summary = routes[0].get("summary") or {}
                distance = summary.get("distance")
                duration = summary.get("duration")

                if distance is None:
                    return None

                distance_km = round(float(distance), 1)
                duration_minutes = round(float(duration) / 60) if duration is not None else None

                print(f"✅ ORS маршрут: {distance_km} км (~{duration_minutes} мин.)")
                return {
                    "distance_km": distance_km,
                    "duration_minutes": duration_minutes,
                }
    except Exception as error:
        print("❌ Ошибка ORS:", repr(error))
        return None


# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ РАСЧЁТА
# ============================================================

async def get_route_distance(from_address, to_address):
    print()
    print("=" * 60)
    print(f"РАСЧЁТ МАРШРУТА: '{from_address}' ➔ '{to_address}'")
    print("=" * 60)

    from_point = await geocode_exact_address(from_address)
    if not from_point:
        print(f"❌ Не удалось найти адрес отправления: {from_address}")
        return None

    to_point = await geocode_exact_address(to_address)
    if not to_point:
        print(f"❌ Не удалось найти адрес назначения: {to_address}")
        return None

    route = await build_route(
        from_lat=from_point["lat"],
        from_lon=from_point["lon"],
        to_lat=to_point["lat"],
        to_lon=to_point["lon"]
    )

    if not route:
        return None

    return route["distance_km"]