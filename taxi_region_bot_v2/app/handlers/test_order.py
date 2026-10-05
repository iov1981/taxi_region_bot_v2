from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import get_admin_id

from app.services.ai_parser import parse_request
from app.services.route_service import get_route_distance
from app.services.pricing import (
    calculate_price,
    format_price
)


router = Router()

print("test_order.py загружен")


# ============================================================
# ТЕСТОВАЯ ЗАЯВКА
# ============================================================

@router.message(Command("test_order"))
async def test_order(message: Message):

    print()
    print("=" * 60)
    print("ПОЛУЧЕНА КОМАНДА /test_order")
    print("USER ID:", message.from_user.id)
    print("TEXT:", message.text)
    print("=" * 60)

    # --------------------------------------------------------
    # Только администратор
    # --------------------------------------------------------

    if message.from_user.id != get_admin_id():

        print(
            "Доступ запрещён. USER ID:",
            message.from_user.id
        )

        return

    # --------------------------------------------------------
    # Получаем аргументы после команды
    # --------------------------------------------------------

    test_text = message.text or ""

    parts = test_text.split(
        maxsplit=1
    )

    if len(parts) > 1:
        test_text = parts[1].strip()
    else:
        test_text = ""

    # --------------------------------------------------------
    # Если текст не указан
    # --------------------------------------------------------

    if not test_text:

        await message.answer(
            "🧪 <b>ТЕСТОВЫЙ РЕЖИМ</b>\n\n"

            "Укажите текст заявки после команды.\n\n"

            "<b>Пример:</b>\n"
            "/test_order Пенза — Воробьевка\n\n"

            "<b>С адресами:</b>\n"
            "/test_order "
            "Пенза Ленина 25 — "
            "Воробьевка Советская 10, "
            "2 человека утром",
            parse_mode="HTML"
        )

        return

    # --------------------------------------------------------
    # Показываем запуск теста
    # --------------------------------------------------------

    await message.answer(
        "🧪 <b>Запускаю тест заявки...</b>\n\n"
        f"📝 {test_text}",
        parse_mode="HTML"
    )

    print()
    print("=" * 60)
    print("ТЕСТОВАЯ ЗАЯВКА")
    print("=" * 60)
    print("ТЕКСТ:", test_text)
    print("=" * 60)

    # ========================================================
    # ПАРСИНГ
    # ========================================================

    try:

        parsed = await parse_request(
            test_text
        )

    except Exception as error:

        print(
            "ОШИБКА ПАРСЕРА:",
            repr(error)
        )

        await message.answer(
            "❌ <b>Ошибка при разборе заявки.</b>\n\n"
            f"{error}",
            parse_mode="HTML"
        )

        return

    # ========================================================
    # ПОЛУЧАЕМ ДАННЫЕ
    # ========================================================

    from_place = parsed.get(
        "from_place"
    )

    to_place = parsed.get(
        "to_place"
    )

    from_address = parsed.get(
        "from_address"
    )

    to_address = parsed.get(
        "to_address"
    )

    date = parsed.get(
        "date",
        "не указана"
    )

    time = parsed.get(
        "time",
        "не указано"
    )

    passengers = parsed.get(
        "passengers",
        "не указано"
    )

    # --------------------------------------------------------
    # Защита от None
    # --------------------------------------------------------

    if not from_place:
        from_place = "не определено"

    if not to_place:
        to_place = "не определено"

    if not from_address:
        from_address = "не указан"

    if not to_address:
        to_address = "не указан"

    # ========================================================
    # ТИП ПОЕЗДКИ
    # ========================================================

    city_places = {
        "Пенза",
        "Заречный"
    }

    city_trip = (
        from_place in city_places
        and to_place in city_places
    )

    if from_place == to_place:
        city_trip = True

    trip_type = (
        "🏙 Городская поездка"
        if city_trip
        else "🛣 Межгород"
    )

    # ========================================================
    # ВЫВОД ПАРСЕРА
    # ========================================================

    print()
    print("РЕЗУЛЬТАТ ПАРСЕРА")
    print("-" * 60)

    print(
        "ОТКУДА:",
        from_place
    )

    print(
        "КУДА:",
        to_place
    )

    print(
        "АДРЕС ОТКУДА:",
        from_address
    )

    print(
        "АДРЕС КУДА:",
        to_address
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

    print("-" * 60)

    # ========================================================
    # ТОЧКИ МАРШРУТА
    # ========================================================

    route_from = (
        from_address
        if from_address != "не указан"
        else from_place
    )

    route_to = (
        to_address
        if to_address != "не указан"
        else to_place
    )

    # ========================================================
    # МАРШРУТ И ЦЕНА
    # ========================================================

    distance_km = None
    price = None

    if (
        route_from != "не определено"
        and route_to != "не определено"
    ):

        print()
        print("ПОСТРОЕНИЕ МАРШРУТА")
        print("-" * 60)

        print(
            "ОТКУДА:",
            route_from
        )

        print(
            "КУДА:",
            route_to
        )

        try:

            distance_km = await get_route_distance(
                route_from,
                route_to
            )

            if distance_km is not None:

                price = calculate_price(
                    distance_km,
                    is_intercity=not city_trip
                )

                print(
                    "РАССТОЯНИЕ:",
                    distance_km,
                    "км"
                )

                print(
                    "ЦЕНА:",
                    price,
                    "₽"
                )

            else:

                print(
                    "РАССТОЯНИЕ НЕ ОПРЕДЕЛЕНО"
                )

        except Exception as error:

            print(
                "ОШИБКА МАРШРУТА:",
                repr(error)
            )

    # ========================================================
    # ФОРМИРУЕМ РЕЗУЛЬТАТ
    # ========================================================

    result = (
        "🧪 <b>РЕЗУЛЬТАТ ТЕСТА</b>\n\n"

        f"📍 <b>Откуда:</b> "
        f"{from_place}\n"

        f"🏁 <b>Куда:</b> "
        f"{to_place}\n\n"

        f"📍 <b>Адрес откуда:</b>\n"
        f"{from_address}\n\n"

        f"🏁 <b>Адрес куда:</b>\n"
        f"{to_address}\n\n"

        f"{trip_type}\n"

        f"📅 <b>Дата:</b> "
        f"{date}\n"

        f"🕐 <b>Время:</b> "
        f"{time}\n"

        f"👥 <b>Пассажиров:</b> "
        f"{passengers}\n\n"
    )

    # ========================================================
    # РАССТОЯНИЕ
    # ========================================================

    if distance_km is not None:

        result += (
            f"📏 <b>Расстояние:</b> "
            f"{distance_km} км\n"
        )

    else:

        result += (
            "📏 <b>Расстояние:</b> "
            "не определено\n"
        )

    # ========================================================
    # ЦЕНА
    # ========================================================

    if price is not None:

        result += (
            f"💰 <b>Стоимость:</b> "
            f"{format_price(price)}\n"
        )

    else:

        result += (
            "💰 <b>Стоимость:</b> "
            "не определена\n"
        )

    # ========================================================
    # ИСХОДНЫЙ ТЕКСТ
    # ========================================================

    result += (
        "\n"
        "📝 <b>Исходный текст:</b>\n"
        f"{test_text}\n\n"

        "ℹ️ <b>Тестовая заявка НЕ записана в БД.</b>"
    )

    # ========================================================
    # ОТВЕТ
    # ========================================================

    await message.answer(
        result,
        parse_mode="HTML"
    )

    print()
    print("=" * 60)
    print("ТЕСТ ЗАВЕРШЁН")
    print("=" * 60)
    print()