# =====================================
# ТАРИФЫ ТАКСИ
# =====================================

# Городской тариф:
# Подача (включает первые 2 км) + цена за каждый последующий км
CITY_BASE_PRICE = 200  # Базовая стоимость подачи
CITY_INCLUDED_KM = 2.0  # Километры, включённые в базовую стоимость
CITY_PRICE_PER_KM = 35  # Стоимость за 1 км сверх включённых
MIN_CITY_PRICE = 300  # Минимальная цена по городу

# Межгород:
# Оплата за км + минимальный порог
INTERCITY_BASE_PRICE = 250  # Подача на межгород
INTERCITY_PRICE_PER_KM = 25  # Стоимость за 1 км
MIN_INTERCITY_PRICE = 500  # Минимальная цена межгорода


# =====================================
# Расчёт стоимости
# =====================================

def calculate_price(
        distance_km: float,
        is_intercity: bool = False
) -> int:
    try:
        distance_km = float(distance_km)
    except (TypeError, ValueError):
        distance_km = 0.0

    if is_intercity:
        # Межгород: базовая подача + ставка за километр
        price = INTERCITY_BASE_PRICE + (distance_km * INTERCITY_PRICE_PER_KM)
        price = max(price, MIN_INTERCITY_PRICE)
    else:
        # Город: если поездка больше включённого расстояния, начисляем за каждый км
        if distance_km <= CITY_INCLUDED_KM:
            price = CITY_BASE_PRICE
        else:
            extra_km = distance_km - CITY_INCLUDED_KM
            price = CITY_BASE_PRICE + (extra_km * CITY_PRICE_PER_KM)

        price = max(price, MIN_CITY_PRICE)

    return round(price)


# =====================================
# Отображение цены
# =====================================

def format_price(price) -> str:
    if price is None:
        return "уточняется"
    return f"{round(price):,}".replace(",", " ") + " ₽"