# =====================================
# ТАРИФЫ ТАКСИ
# =====================================

# Стоимость 1 км
CITY_PRICE_PER_KM = 35
INTERCITY_PRICE_PER_KM = 20

# Минимальная стоимость поездки
MIN_CITY_PRICE = 300
MIN_INTERCITY_PRICE = 500


# =====================================
# Расчёт стоимости
# =====================================

def calculate_price(
        distance_km,
        is_intercity=False
):

    distance_km = float(distance_km)

    if is_intercity:

        price = (
            distance_km *
            INTERCITY_PRICE_PER_KM
        )

        price = max(
            price,
            MIN_INTERCITY_PRICE
        )

    else:

        price = (
            distance_km *
            CITY_PRICE_PER_KM
        )

        price = max(
            price,
            MIN_CITY_PRICE
        )

    return round(price)


# =====================================
# Красивое отображение цены
# =====================================

def format_price(price):

    return f"{price:,}".replace(",", " ") + " ₽"