import os
import aiohttp


async def get_yandex_price(from_lon, from_lat, to_lon, to_lat):
    clid = os.getenv("YANDEX_CLID")
    api_key = os.getenv("YANDEX_API_KEY")

    if not clid or not api_key:
        return {"ok": False, "message": "YANDEX_CLID/YANDEX_API_KEY не настроены"}

    params = {
        "clid": clid,
        "apikey": api_key,
        "rll": f"{from_lon},{from_lat}~{to_lon},{to_lat}",
        "class": "econom",
        "lang": "ru",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://taxi-routeinfo.taxi.yandex.net/taxi_info",
            params=params,
            timeout=20,
        ) as response:
            if response.status != 200:
                return {"ok": False, "message": f"HTTP {response.status}"}
            return {"ok": True, "data": await response.json()}
