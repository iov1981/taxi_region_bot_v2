from typing import Dict, Any, Optional

CITY_BASE_PRICE = 200
CITY_BASE_KM = 2.0
CITY_PER_KM = 35

INTERCITY_PER_KM = 30
INTERCITY_MIN_PRICE = 300

CHILD_CHAIR_PRICE = 100


def calculate_price(distance_km: Optional[float], has_child_chair: bool = False) -> Optional[Dict[str, Any]]:
    if distance_km is None:
        return None

    is_city = distance_km <= 15.0

    if is_city:
        if distance_km <= CITY_BASE_KM:
            base = CITY_BASE_PRICE
        else:
            extra_km = distance_km - CITY_BASE_KM
            base = CITY_BASE_PRICE + (extra_km * CITY_PER_KM)
    else:
        calculated = distance_km * INTERCITY_PER_KM
        base = max(calculated, INTERCITY_MIN_PRICE)

    extra = CHILD_CHAIR_PRICE if has_child_chair else 0
    total_price = round(base + extra)

    return {
        "price": total_price,
        "is_city": is_city,
        "distance_km": distance_km,
        "has_child_chair": has_child_chair
    }