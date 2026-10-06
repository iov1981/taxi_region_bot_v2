from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import get_admin_id, get_drivers_chat_id

from app.db import (
    create_request,
    save_admin_message_id,
    get_request
)

from app.services.ai_parser import parse_request
from app.services.route_service import get_route_distance
from app.services.pricing import calculate_price, format_price


router = Router()

print("test_real_order.py загружен")


# ============================================================
# КЛАВИАТУРА ДЛЯ ВОДИТЕЛЕЙ
# ============================================================

def drivers_order_keyboard(request_id):

    builder = InlineKeyboardBuilder()

    builder.button(
        text="🟢 БЕРУ ЗАКАЗ",
        callback_data=f"driver_wants:{request_id}"
    )

    return builder.as_markup()


# ============================================================
# ТЕСТОВАЯ РЕАЛЬНАЯ ЗАЯВКА
# ============================================================

@router.message(Command("test_real_order"))
async def test_real_order(message: Message):

    print()
    print("=" * 60)
    print("ПОЛУЧЕНА КОМАНДА /test_real_order")
    print("USER ID:", message.from_user.id)
    print("TEXT:", message.text)
    print("=" * 60)

    # ========================================================
    # ТОЛЬКО АДМИНИСТРАТОР
    # ========================================================

    if message.from_user.id != get_admin_id():

        print(
            "Доступ запрещён. USER ID:",
            message.from_user.id
        )

        return

    # ========================================================
    # ПОЛУЧАЕМ ТЕКСТ ПОСЛЕ КОМАНДЫ
    # ========================================================

    command_text = message.text or ""

    parts = command_text.split(
        maxsplit=1
    )

    if len(parts) > 1:

        test_text = parts[1].strip()

    else:

        test_text = ""

    if not test_text:

        await message.answer(
            "🧪 <b>ТЕСТ РЕАЛЬНОГО ЗАКАЗА</b>\n\n"
            "Укажите текст заявки после команды.\n\n"
            "<b>Пример:</b>\n"
            "/test_real_order Пенза Воробьевка, 2 человека\n\n"
            "<b>С адресами:</b>\n"
            "/test_real_order "
            "Пенза Ленина 25 — "
            "Воробьевка Советская 10, "
            "2 человека",
            parse_mode="HTML"
        )

        return

    # ========================================================
    # НАЧАЛО ТЕСТА
    # ========================================================

    await message.answer(
        "🧪 <b>Запускаю тест реального заказа...</b>\n\n"
        f"📝 {test_text}\n\n"
        "Заявка будет записана в БД.",
        parse_mode="HTML"
    )

    print()
    print("=" * 60)
    print("ТЕСТ РЕАЛЬНОГО ЗАКАЗА")
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
            "❌ ОШИБКА ПАРСЕРА:",
            repr(error)
        )

        await message.answer(
            "❌ <b>Ошибка при разборе заявки.</b>\n\n"
            f"{error}",
            parse_mode="HTML"
        )

        return

    # ========================================================
    # ДАННЫЕ ПАРСЕРА
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

    if not from_place:
        from_place = "не определено"

    if not to_place:
        to_place = "не определено"

    if not from_address:
        from_address = "не указан"

    if not to_address:
        to_address = "не указан"

    print()
    print("РЕЗУЛЬТАТ ПАРСЕРА")
    print("-" * 60)
    print("ОТКУДА:", from_place)
    print("КУДА:", to_place)
    print("АДРЕС ОТКУДА:", from_address)
    print("АДРЕС КУДА:", to_address)
    print("ДАТА:", date)
    print("ВРЕМЯ:", time)
    print("ПАССАЖИРОВ:", passengers)
    print("-" * 60)

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

    distance_km = None
    price = None

    # ========================================================
    # ПОСТРОЕНИЕ МАРШРУТА
    # ========================================================

    print()
    print("=" * 60)
    print("ПОСТРОЕНИЕ МАРШРУТА")
    print("=" * 60)
    print("ОТКУДА:", route_from)
    print("КУДА:", route_to)
    print("=" * 60)

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
                "⚠️ РАССТОЯНИЕ НЕ ОПРЕДЕЛЕНО"
            )

    except Exception as error:

        print(
            "❌ ОШИБКА МАРШРУТА:",
            repr(error)
        )

    # ========================================================
    # КРАТКАЯ ИНФОРМАЦИЯ О ЗАКАЗЕ
    # ========================================================

    ai_summary = (
        f"📍 <b>Откуда:</b> {from_place}\n"
        f"🏁 <b>Куда:</b> {to_place}\n"
        f"{trip_type}\n"
        f"📅 <b>Дата:</b> {date}\n"
        f"🕐 <b>Время:</b> {time}\n"
        f"👥 <b>Пассажиров:</b> {passengers}\n"
    )

    if distance_km is not None:

        ai_summary += (
            f"📏 <b>Расстояние:</b> "
            f"{distance_km} км\n"
        )

    else:

        ai_summary += (
            "📏 <b>Расстояние:</b> "
            "не определено\n"
        )

    if price is not None:

        ai_summary += (
            f"💰 <b>Стоимость:</b> "
            f"{format_price(price)}\n"
        )

    else:

        ai_summary += (
            "💰 <b>Стоимость:</b> "
            "не определена\n"
        )

    # ========================================================
    # СОЗДАЁМ ЗАПИСЬ В БД
    # ========================================================

    print()
    print("=" * 60)
    print("СОЗДАНИЕ ЗАКАЗА В БД")
    print("=" * 60)

    try:

        request_id = await create_request(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            raw_text=test_text,
            ai_summary=ai_summary,
            distance_km=distance_km,
            price=price
        )

    except Exception as error:

        print()
        print(
            "❌ ОШИБКА СОЗДАНИЯ ЗАКАЗА:"
        )

        print(
            type(error).__name__,
            repr(error)
        )

        await message.answer(
            "❌ <b>Не удалось создать заказ в БД.</b>\n\n"
            f"{error}",
            parse_mode="HTML"
        )

        return

    print(
        "✅ ЗАКАЗ СОЗДАН"
    )

    print(
        "REQUEST ID:",
        request_id
    )

    print(
        "DISTANCE:",
        distance_km
    )

    print(
        "PRICE:",
        price
    )

    # ========================================================
    # ПОЛУЧАЕМ ЗАКАЗ ИЗ БД
    # ========================================================

    request = await get_request(
        request_id
    )

    if not request:

        print(
            "❌ ЗАКАЗ СОЗДАН, НО НЕ НАЙДЕН В БД"
        )

        await message.answer(
            "❌ Заказ создан, но не удалось "
            "прочитать его из БД."
        )

        return

    print(
        "✅ ЗАКАЗ ПРОЧИТАН ИЗ БД"
    )

    # ========================================================
    # ИМЯ КЛИЕНТА
    # ========================================================

    if message.from_user.username:

        client_name = (
            f"@{message.from_user.username}"
        )

    else:

        client_name = (
            message.from_user.first_name
            or "не указан"
        )

    # ========================================================
    # КАРТОЧКА АДМИНИСТРАТОРА
    # ========================================================

    admin_text = (
        f"🧪 <b>ТЕСТОВЫЙ ЗАКАЗ №{request_id}</b>\n\n"
        f"👤 <b>Клиент:</b> {client_name}\n"
        f"🆔 <b>ID:</b> {message.from_user.id}\n"
        f"📞 <b>Телефон:</b> не указан\n\n"
        f"{ai_summary}\n"
        f"📊 <b>Статус:</b> 🟢 Новый\n"
        f"🚕 <b>Водитель:</b> —\n\n"
        f"📝 <b>Сообщение клиента:</b>\n"
        f"{test_text}"
    )

    # ========================================================
    # ОТПРАВЛЯЕМ КАРТОЧКУ АДМИНУ
    # ========================================================

    print()
    print("=" * 60)
    print("ОТПРАВКА КАРТОЧКИ АДМИНУ")
    print("=" * 60)
    print(
        "ADMIN ID:",
        get_admin_id()
    )
    print(
        "REQUEST ID:",
        request_id
    )
    print("=" * 60)

    try:

        from app.handlers.admin import order_keyboard

        admin_message = await message.bot.send_message(
            get_admin_id(),
            admin_text,
            parse_mode="HTML",
            reply_markup=order_keyboard(
                request
            )
        )

        print(
            "✅ КАРТОЧКА АДМИНА ОТПРАВЛЕНА"
        )

        print(
            "ADMIN MESSAGE ID:",
            admin_message.message_id
        )

        # ----------------------------------------------------
        # Сохраняем ID сообщения администратора
        # ----------------------------------------------------

        from app.db import save_admin_message_id

        await save_admin_message_id(
            request_id,
            admin_message.message_id
        )

        print(
            "✅ admin_message_id СОХРАНЁН"
        )

    except Exception as error:

        print()
        print(
            "❌ ОШИБКА ОТПРАВКИ КАРТОЧКИ АДМИНУ:"
        )

        print(
            type(error).__name__,
            repr(error)
        )

    # ========================================================
    # ОТПРАВКА ЗАКАЗА В ГРУППУ ВОДИТЕЛЕЙ
    # ========================================================

    driver_text = (
        f"🧪 <b>ТЕСТОВЫЙ ЗАКАЗ №{request_id}</b>\n\n"
        f"📍 <b>Откуда:</b> {from_place}\n"
        f"🏁 <b>Куда:</b> {to_place}\n"
        f"{trip_type}\n"
        f"📅 <b>Дата:</b> {date}\n"
        f"🕐 <b>Время:</b> {time}\n"
        f"👥 <b>Пассажиров:</b> {passengers}\n"
    )

    if distance_km is not None:

        driver_text += (
            f"📏 <b>Расстояние:</b> "
            f"{distance_km} км\n"
        )

    if price is not None:

        driver_text += (
            f"💰 <b>Стоимость:</b> "
            f"{format_price(price)}\n"
        )

    print()
    print("=" * 60)
    print("ОТПРАВКА ТЕСТОВОГО ЗАКАЗА ВОДИТЕЛЯМ")
    print("=" * 60)
    print(
        "DRIVERS CHAT ID:",
        get_drivers_chat_id()
    )
    print(
        "REQUEST ID:",
        request_id
    )
    print("=" * 60)

    try:

        driver_message = await message.bot.send_message(
            get_drivers_chat_id(),
            driver_text,
            parse_mode="HTML",
            reply_markup=drivers_order_keyboard(
                request_id
            )
        )

        print(
            "✅ ЗАКАЗ ОТПРАВЛЕН В ГРУППУ ВОДИТЕЛЕЙ"
        )

        print(
            "DRIVER MESSAGE ID:",
            driver_message.message_id
        )

        print(
            "✅ КНОПКА 🟢 БЕРУ ЗАКАЗ ДОБАВЛЕНА"
        )

    except Exception as error:

        print()
        print(
            "❌ ОШИБКА ОТПРАВКИ ЗАКАЗА ВОДИТЕЛЯМ"
        )

        print(
            type(error).__name__,
            repr(error)
        )

    # ========================================================
    # ОТВЕТ АДМИНИСТРАТОРУ
    # ========================================================

    result = (
        "✅ <b>ТЕСТОВЫЙ ЗАКАЗ СОЗДАН</b>\n\n"
        f"🚕 <b>Номер заказа:</b> №{request_id}\n\n"
        f"{ai_summary}\n"
        "📞 <b>Телефон:</b> не указан\n"
        "📊 <b>Статус:</b> 🟢 Новый\n\n"
        "💾 <b>Заказ записан в SQLite.</b>\n"
        "📨 Карточка отправлена администратору.\n"
        "🚕 Заказ отправлен в группу водителей."
    )

    await message.answer(
        result,
        parse_mode="HTML"
    )

    print()
    print("=" * 60)
    print("ТЕСТ РЕАЛЬНОГО ЗАКАЗА ЗАВЕРШЁН")
    print("НОМЕР ЗАКАЗА:", request_id)
    print("=" * 60)
    print()