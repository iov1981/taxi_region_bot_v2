import os
import re
import aiohttp
from typing import Optional, Tuple, Dict

ORS_API_KEY = os.getenv("ORS_API_KEY", "").strip()
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY", "").strip()

PENZA_CENTER_LON = 45.0189
PENZA_CENTER_LAT = 53.2036

LANDMARKS: Dict[str, Tuple[float, float]] = {
    "вокзал": (45.0189, 53.2036),
    "пенза 1": (45.0189, 53.2036),
    "пенза-1": (45.0189, 53.2036),
    "ж/д вокзал": (45.0189, 53.2036),
    "жд вокзал": (45.0189, 53.2036),
    "главный вокзал": (45.0189, 53.2036),
    "пенза 2": (45.0512, 53.1895),
    "пенза-2": (45.0512, 53.1895),
    "пенза 3": (45.0035, 53.1724),
    "пенза-3": (45.0035, 53.1724),
    "пенза 4": (44.9752, 53.2384),
    "автовокзал": (45.0215, 53.2114),
    "аэропорт": (45.0223, 53.1186),
    "коллаж": (44.9452, 53.2201),
    "трц коллаж": (44.9452, 53.2201),
    "тц коллаж": (44.9452, 53.2201),
    "пассаж": (45.0152, 53.1947),
    "цум": (45.0163, 53.1959),
    "суворовский": (45.0068, 53.2014),
    "санмарт": (44.9924, 53.2065),
    "красные холмы": (45.0095, 53.2148),
    "центральный рынок": (45.0118, 53.1962),
    "областная больница": (45.0042, 53.1795),
    "больница бурденко": (45.0042, 53.1795),
    "онкодиспансер": (44.9495, 53.2374),
    "детская областная": (44.9825, 53.2285),
    "кардиоцентр": (44.9421, 53.2356),
    "пгу": (45.0038, 53.1812),
    "пгта": (45.0255, 53.2185),
    "пензгту": (45.0255, 53.2185),
    "пгуас": (44.9814, 53.2215)
}


def check_landmark(query: str) -> Optional[Tuple[float, float]]:
    clean = re.sub(r"[^\w\s-]", "", query.lower()).strip()
    return LANDMARKS.get(clean)


async def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    if not address or not address.strip():
        return None

    query = address.strip()

    coords = check_landmark(query)
    if coords:
        print(f"🎯 ОРИЕНТИР НАЙДЕН В СЛОВАРЕ: '{query}' -> {coords}")
        return coords

    coord_match = re.match(r"^(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)$", query)
    if coord_match:
        lat = float(coord_match.group(1))
        lon = float(coord_match.group(2))
        return lon, lat

    if not GEOAPIFY_API_KEY:
        print("❌ GEOAPIFY_API_KEY не задан")
        return None

    lower_query = query.lower()
    other_cities = [
        "кузнецк", "заречный", "каменка", "сердобск", "нижний ломов",
        "никольск", "белинский", "городище", "лунино", "мокшан", "земетчино",
        "бессоновка", "пыркино", "засечное", "спутник", "саратов", "саранск"
    ]
    is_external_city = any(c in lower_query for c in other_cities)

    if is_external_city:
        queries = [f"Пензенская область, {query}", query]
        use_penza_filter = False
    else:
        queries = [f"Россия, Пенза, {query}", f"Пенза, {query}", query]
        use_penza_filter = True

    async with aiohttp.ClientSession() as session:
        for q in queries:
            url = "https://api.geoapify.com/v1/geocode/search"
            params = {
                "text": q,
                "apiKey": GEOAPIFY_API_KEY,
                "lang": "ru",
                "limit": 1
            }

            if use_penza_filter:
                params["bias"] = f"proximity:{PENZA_CENTER_LON},{PENZA_CENTER_LAT}"
                params["filter"] = f"circle:{PENZA_CENTER_LON},{PENZA_CENTER_LAT},30000"

            try:
                async with session.get(url, params=params, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        features = data.get("features", [])
                        if features:
                            lon, lat = features[0]["geometry"]["coordinates"]
                            props = features[0].get("properties", {})
                            formatted = props.get("formatted", q)
                            print(f"✅ Точка найдена: {formatted} -> ({lat}, {lon})")
                            return lon, lat
            except Exception as e:
                print(f"Ошибка запроса Geoapify '{q}':", repr(e))

        if use_penza_filter:
            try:
                fallback_params = {
                    "text": f"Пензенская область, {query}",
                    "apiKey": GEOAPIFY_API_KEY,
                    "lang": "ru",
                    "limit": 1
                }
                async with session.get("https://api.geoapify.com/v1/geocode/search", params=fallback_params, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        features = data.get("features", [])
                        if features:
                            lon, lat = features[0]["geometry"]["coordinates"]
                            props = features[0].get("properties", {})
                            formatted = props.get("formatted", query)
                            print(f"✅ Точка найдена (fallback): {formatted} -> ({lat}, {lon})")
                            return lon, lat
            except Exception as e:
                print("Ошибка fallback Geoapify:", repr(e))

    print(f"❌ Не удалось найти координаты для адреса: {address}")
    return None


async def get_route_distance(from_address: str, to_address: str) -> Optional[float]:
    print()
    print("=" * 60)
    print(f"РАСЧЁТ МАРШРУТА: '{from_address}' ➔ '{to_address}'")
    print("=" * 60)

    from_coords = await geocode_address(from_address)
    if not from_coords:
        print(f"❌ Не удалось найти адрес отправления: {from_address}")
        return None

    to_coords = await geocode_address(to_address)
    if not to_coords:
        print(f"❌ Не удалось найти адрес назначения: {to_address}")
        return None

    if not ORS_API_KEY:
        print("❌ ORS_API_KEY не задан")
        return None

    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json; charset=utf-8"
    }
    body = {
        "coordinates": [
            [from_coords[0], from_coords[1]],
            [to_coords[0], to_coords[1]]
        ]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=headers, timeout=8) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    routes = data.get("routes", [])
                    if routes:
                        summary = routes[0].get("summary", {})
                        distance_meters = summary.get("distance", 0)
                        distance_km = round(distance_meters / 1000.0, 1)
                        print(f"✅ Маршрут построен успешно: {distance_km} км")
                        return distance_km
                else:
                    err_text = await resp.text()
                    print(f"❌ Ошибка OpenRouteService ({resp.status}): {err_text}")
    except Exception as e:
        print("❌ Исключение при запросе к OpenRouteService:", repr(e))

    return None