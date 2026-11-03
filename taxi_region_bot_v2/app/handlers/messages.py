import html
import json
from html.parser import HTMLParser
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import (
    Message,
    KeyboardButton,
    ReplyKeyboardMarkup
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import get_admin_id, get_drivers_chat_id
from app.db import (
    create_request,
    save_phone,
    save_admin_message_id,
    get_request
)
from app.services.ai_parser import parse_request, KNOWN_PLACES
from app.services.route_service import get_route_distance
from app.services.pricing import calculate_price, format_price
from app.handlers.start import client_menu


router = Router()

print("messages.py загружен")


# ============================================================
# HTML-ПРОВЕРКА
# ============================================================

class TelegramHTMLValidator(HTMLParser):

    ALLOWED_TAGS = {
        "b",
        "strong",
        "i",
        "em",
        "u",
        "ins",
        "s",
        "strike",
        "del",
        "code",
        "pre",
        "a",
        "tg-spoiler",
        "blockquote",
    }

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.errors = []
        self.open_tags = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag not in self.ALLOWED_TAGS:
            self.errors.append(f"Недопустимый HTML-тег: <{tag}>")
            return
        self.open_tags.append(tag)

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if tag not in self.ALLOWED_TAGS:
            self.errors.append(f"Недопустимый HTML-тег: <{tag}/>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag not in self.ALLOWED_TAGS:
            self.errors.append(f"Недопустимый закрывающий тег: </{tag}>")
            return

        if not self.open_tags:
            self.errors.append(f"Лишний закрывающий тег: </{tag}>")
            return

        if self.open_tags[-1] != tag:
            self.errors.append(
                f"Нарушена вложенность HTML: ожидался </{self.open_tags[-1]}>, получен </{tag}>"
            )
            return

        self.open_tags.pop()

    def handle_comment(self, data):
        self.errors.append("HTML-комментарии запрещены.")


def validate_html(text: str) -> tuple[bool, list[str]]:
    if not isinstance(text, str):
        return False, ["Текст сообщения не является строкой."]

    parser = TelegramHTMLValidator()
    try:
        parser.feed(text)
        parser.close()
    except Exception as error:
        parser.errors.append(f"Ошибка HTML-парсера: {error}")

    if parser.open_tags:
        parser.errors.append(
            "Не закрыты HTML-теги: " + ", ".join(f"<{tag}>" for tag in parser.open_tags)
        )

    return len(parser.errors) == 0, parser.errors


def escape_html(value) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=False)


async def send_html_message(bot, chat_id, text, **kwargs):
    valid, errors = validate_html(text)
    if valid:
        return await bot.send_message(
            chat_id,
            text,
            parse_mode="HTML",
            **kwargs
        )

    print()
    print("=" * 60)
    print("❌ ОШИБКА HTML ПЕРЕД ОТПРАВКОЙ")
    print("=" * 60)
    for error in errors:
        print("HTML:", error)
    print()
    print("ТЕКСТ С ОШИБКОЙ:")
    print(text)
    print("=" * 60)

    safe_text = html.escape(text, quote=False)
    return await bot.send_message(chat_id, safe_text, **kwargs)


# ============================================================
# СЛУЖЕБНЫЕ СООБЩЕНИЯ
# ============================================================

def is_internal_message(text: str) -> bool:
    if not text:
        return False

    text = text.strip()
    internal_prefixes = (
        "ГЕОКОДИРОВАНИЕ:",
        "GEOAPIFY:",
        "GEOAPIFY ПОИСК",
        "ПОСТРОЕНИЕ МАРШРУТА",
        "ROUTE SERVICE",
    )
    for prefix in internal_prefixes:
        if text.startswith(prefix):
            return True

    return False


# ============================================================
# КНОПКА ДЛЯ ВОДИТЕЛЯ
# ============================================================

def drivers_order_keyboard(request_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🟢 БЕРУ ЗАКАЗ",
        callback_data=f"driver_wants:{request_id}"
    )
    return builder.as_markup()


# ============================================================
# ОБНОВЛЕНИЕ КАРТОЧКИ АДМИНИСТРАТОРА
# ============================================================

async def update_admin_order_card(message: Message, request: dict, phone: str):
    try:
        admin_message_id = request.get("admin_message_id") if isinstance(request, dict) else request["admin_message_id"]
        if not admin_message_id:
            print("⚠️ У заявки нет admin_message_id")
            return

        from app.handlers.admin import order_keyboard

        if message.from_user.username:
            client_name = f"@{message.from_user.username}"
        else:
            client_name = message.from_user.first_name or "не указан"

        req_id = request.get("id") if isinstance(request, dict) else request["id"]
        ai_summary = request.get("ai_summary") if isinstance(request, dict) else request["ai_summary"]
        raw_text = request.get("raw_text") if isinstance(request, dict) else request["raw_text"]

        updated_admin_text = (
            f"🚕 <b>НОВАЯ ЗАЯВКА №{req_id}</b>\n\n"
            f"👤 <b>Клиент:</b> {escape_html(client_name)}\n"
            f"🆔 <b>ID:</b> {escape_html(message.from_user.id)}\n"
            f"📞 <b>Телефон:</b> {escape_html(phone)}\n\n"
            f"{ai_summary}\n"
            f"📝 <b>Сообщение клиента:</b>\n"
            f"{escape_html(raw_text)}"
        )

        valid, errors = validate_html(updated_admin_text)
        if not valid:
            print("❌ HTML карточки администратора не прошёл проверку.")
            return

        await message.bot.edit_message_text(
            chat_id=get_admin_id(),
            message_id=admin_message_id,
            text=updated_admin_text,
            parse_mode="HTML",
            reply_markup=order_keyboard(request)
        )
        print("✅ КАРТОЧКА АДМИНА ОБНОВЛЕНА ТЕЛЕФОНОМ")
    except Exception as error:
        print("❌ ОШИБКА ОБНОВЛЕНИЯ КАРТОЧКИ АДМИНА:", repr(error))


# ============================================================
# СОХРАНЕНИЕ ТЕЛЕФОНА
# ============================================================

async def process_phone(message: Message, phone: str):
    phone = phone.strip()
    print()
    print("=" * 60)
    print("ПОЛУЧЕН ТЕЛЕФОН КЛИЕНТА")
    print("USER ID:", message.from_user.id)
    print("PHONE:", phone)
    print("=" * 60)

    try:
        request = await save_phone(message.from_user.id, phone)
        if not request:
            await message.answer(
                "⚠️ У вас пока нет активной заявки.\n\nСначала отправьте маршрут поездки.",
                reply_markup=client_menu()
            )
            return True

        request_id = request.get("id") if isinstance(request, dict) else request["id"]
        print("ЗАЯВКА ДЛЯ ТЕЛЕФОНА:", request_id)

        await update_admin_order_card(message, request, phone)

        driver_id = request.get("driver_id") if isinstance(request, dict) else request["driver_id"]
        if driver_id:
            try:
                await send_html_message(
                    message.bot,
                    driver_id,
                    f"📞 <b>Клиент по заказу №{request_id} указал номер:</b> {escape_html(phone)}"
                )
                print(f"✅ Телефон отправлен назначенному водителю (ID: {driver_id})")
            except Exception as driver_err:
                print(f"⚠️ Ошибка отправки номера водителю: {driver_err}")

        await send_html_message(
            message.bot,
            message.chat.id,
            "📞 <b>Телефон сохранён.</b>\n\nВодитель и администратор оповещены.",
            reply_markup=client_menu()
        )
        print(f"✅ ТЕЛЕФОН СОХРАНЁН ДЛЯ ЗАКАЗА №{request_id}")
        return True
    except Exception as error:
        print("❌ ОШИБКА СОХРАНЕНИЯ ТЕЛЕФОНА:", repr(error))
        await message.answer(
            "❌ Не удалось сохранить номер телефона.\nПопробуйте отправить его ещё раз.",
            reply_markup=client_menu()
        )
        return True


# ============================================================
# ВРЕМЯ И ФОРМАТИРОВАНИЕ ДЛЯ MINI APP
# ============================================================

def get_moscow_now() -> datetime:
    return datetime.now(ZoneInfo("Europe/Moscow"))


def get_mini_app_time_text(data: dict) -> str:
    selected_time = str(data.get("selected_time", "")).strip().lower()
    time_type = str(data.get("time_type", "")).strip().lower()
    time_value = str(data.get("time", "")).strip()
    date_value = str(data.get("date", "")).strip()
    raw_text = str(data.get("text", "")).strip().lower()

    if selected_time in {"now", "сейчас"} or time_type in {"now", "сейчас"}:
        return "сейчас"
    if selected_time in {"30min", "30", "через 30 минут"} or time_type in {"30min", "30", "через 30 минут"}:
        return "через 30 минут"
    if selected_time in {"tomorrow", "завтра"} or time_type in {"tomorrow", "завтра"}:
        return f"завтра в {time_value}" if time_value else "завтра"

    if "сейчас" in raw_text:
        return "сейчас"
    if "через 30 минут" in raw_text:
        return "через 30 минут"

    if date_value and time_value:
        return f"{date_value} в {time_value}"
    if time_value:
        return time_value
    if date_value:
        return date_value
    return ""


def clean_mini_app_route_text(text: str) -> str:
    if not text:
        return text

    result = str(text).strip()
    time_markers = (
        "через 30 минут",
        "через час",
        "через 1 час",
        "сейчас",
        "завтра",
        "послезавтра",
    )

    for marker in time_markers:
        result = result.replace(f", {marker}", "")
        lower_result = result.lower()
        if lower_result.endswith(f" {marker}"):
            result = result[:len(result) - len(marker)].rstrip(" ,")

    return result.strip()


def build_mini_app_text(data: dict) -> str:
    from_place = str(data.get("from", "")).strip()
    to_place = str(data.get("to", "")).strip()
    passengers = data.get("passengers", 1)

    try:
        passengers = int(passengers)
    except (TypeError, ValueError):
        passengers = 1
    if passengers < 1:
        passengers = 1

    time_text = get_mini_app_time_text(data)
    comment = str(data.get("comment", "")).strip()

    result = f"{from_place} — {to_place}, {passengers} человек"
    if time_text:
        result += f", {time_text}"
    if comment:
        result += f", {comment}"

    return result.strip()


# ============================================================
# ОБРАБОТКА СООБЩЕНИЯ КЛИЕНТА
# ============================================================

@router.message(
    F.chat.id > 0,
    F.text | F.contact | F.web_app_data
)
async def handle_message(message: Message):

    # 1. TELEGRAM КОНТАКТ
    if message.contact:
        phone = message.contact.phone_number.strip()
        print()
        print("=" * 60)
        print("ПОЛУЧЕН КОНТАКТ КЛИЕНТА")
        print("PHONE:", phone)
        print("=" * 60)

        if message.contact.user_id is not None and message.contact.user_id != message.from_user.id:
            await message.answer(
                "⚠️ Пожалуйста, отправьте свой номер телефона.",
                reply_markup=client_menu()
            )
            return

        await process_phone(message, phone)
        return

    # 2. MINI APP ДАННЫЕ
    data = None
    is_mini_app = bool(message.web_app_data)

    if is_mini_app:
        try:
            data = json.loads(message.web_app_data.data)
        except json.JSONDecodeError as error:
            print("❌ ОШИБКА JSON MINI APP:", repr(error))
            await message.answer(
                "❌ Не удалось получить данные заказа из Mini App.",
                reply_markup=client_menu()
            )
            return

        if not isinstance(data, dict):
            await message.answer("❌ Неверный формат заказа.", reply_markup=client_menu())
            return

        from_place_input = str(data.get("from", "")).strip()
        to_place_input = str(data.get("to", "")).strip()

        if not from_place_input or not to_place_input:
            await message.answer(
                "⚠️ Укажите адрес отправления и адрес назначения.",
                reply_markup=client_menu()
            )
            return

        text = build_mini_app_text(data)
    else:
        text = (message.text or "").strip()
        if not text:
            return

    # 3. ЗАЩИТА ОТ СЛУЖЕБНЫХ СООБЩЕНИЙ
    if is_internal_message(text):
        return

    print()
    print("=" * 60)
    print("ПОЛУЧЕНО СООБЩЕНИЕ ОТ КЛИЕНТА")
    print("USER ID:", message.from_user.id)
    print("TEXT:", text)
    print("=" * 60)

    # 4. ПРОВЕРКА ТЕЛЕФОНА ТЕКСТОМ
    phone_text = (
        text.replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )
    if phone_text.startswith("8") and len(phone_text) == 11:
        phone_text = "+7" + phone_text[1:]

    if phone_text.startswith("+7") and phone_text[1:].isdigit() and len(phone_text) == 12:
        await process_phone(message, phone_text)
        return

    # 5. РАЗБОР ЗАЯВКИ ПАРСЕРОМ
    parser_text = clean_mini_app_route_text(text) if is_mini_app else text

    try:
        parsed = await parse_request(parser_text)
    except Exception as error:
        print("ОШИБКА ПАРСЕРА:", repr(error))
        await send_html_message(
            message.bot,
            message.chat.id,
            "❌ <b>Не удалось разобрать заявку.</b>\n\nПример:\nПенза — Воробьевка, 2 человека, завтра",
            reply_markup=client_menu()
        )
        return

    from_place = str(parsed.get("from_place") or "").strip()
    to_place = str(parsed.get("to_place") or "").strip()
    from_address = str(parsed.get("from_address") or "").strip()
    to_address = str(parsed.get("to_address") or "").strip()

    date = parsed.get("date") or "не указана"
    time = parsed.get("time") or "не указано"
    passengers = parsed.get("passengers") or "не указано"

    invalid_values = {
        "", "не определено", "не определен", "не указано",
        "не указан", "unknown", "none", "null"
    }

    if from_place.casefold() in invalid_values or to_place.casefold() in invalid_values:
        await message.answer(
            "⚠️ Не удалось определить маршрут поездки.\n\n"
            "Напишите маршрут подробнее, например:\n"
            "<b>ул. Ленина 5 до вокзала</b> или <b>Пенза — Кузнецк</b>.",
            parse_mode="HTML",
            reply_markup=client_menu()
        )
        return

    if from_address.casefold() in invalid_values:
        from_address = from_place
    if to_address.casefold() in invalid_values:
        to_address = to_place

    if is_mini_app:
        from_address = clean_mini_app_route_text(from_address)
        to_address = clean_mini_app_route_text(to_address)
        from_place = clean_mini_app_route_text(from_place)
        to_place = clean_mini_app_route_text(to_place)

        mini_app_time = get_mini_app_time_text(data)
        if mini_app_time:
            if mini_app_time in {"сейчас", "через 30 минут"}:
                date = get_moscow_now().strftime("%Y-%m-%d")
                time = mini_app_time
            elif mini_app_time.startswith("завтра"):
                date = "завтра"
                time = mini_app_time.split(" в ", 1)[1] if " в " in mini_app_time else "не указано"

    # ========================================================
    # ОПРЕДЕЛЕНИЕ ТИПА ПОЕЗДКИ (ГОРОД / МЕЖГОРОД)
    # ========================================================
    # Список других городов/районов (не входящих в Пензу и ближний пригород)
    intercity_places = [
        p for p in KNOWN_PLACES
        if p not in ("пенза", "заречный")
    ]

    norm_from = from_address.lower() if from_address else from_place.lower()
    norm_to = to_address.lower() if to_address else to_place.lower()

    # Проверяем, упоминается ли другой населённый пункт/город
    from_is_intercity = any(p in norm_from for p in intercity_places)
    to_is_intercity = any(p in norm_to for p in intercity_places)

    # Если в маршруте явно фигурирует другой город — это межгород.
    # Если указаны просто улицы или точки внутри Пензы/Спутника/Заречного — это город.
    is_intercity = from_is_intercity or to_is_intercity
    city_trip = not is_intercity

    trip_type = "🏙 Городская поездка" if city_trip else "🛣 Межгород"

    # ========================================================
    # ПОСТРОЕНИЕ МАРШРУТА И РАСЧЁТ ЦЕНЫ
    # ========================================================
    route_from = from_address if from_address != "не указан" else from_place
    route_to = to_address if to_address != "не указан" else to_place

    distance_km = None
    price = None

    if route_from and route_to:
        try:
            distance_km = await get_route_distance(route_from, route_to)
            if distance_km is not None:
                price = calculate_price(
                    distance_km=distance_km,
                    is_intercity=is_intercity
                )
                print(f"РАССТОЯНИЕ: {distance_km} км | ТИП: {trip_type} | ЦЕНА: {price} ₽")
        except Exception as error:
            print("ОШИБКА МАРШРУТА:", repr(error))

    # ========================================================
    # ФОРМИРОВАНИЕ ИТОГА ЗАЯВКИ
    # ========================================================
    ai_summary = (
        f"📍 <b>Откуда:</b> {escape_html(from_place)}\n"
        f"🏁 <b>Куда:</b> {escape_html(to_place)}\n"
        f"{trip_type}\n"
        f"📅 <b>Дата:</b> {escape_html(date)}\n"
        f"🕐 <b>Время:</b> {escape_html(time)}\n"
        f"👥 <b>Пассажиров:</b> {escape_html(passengers)}\n"
    )

    if distance_km is not None:
        ai_summary += f"📏 <b>Расстояние:</b> {escape_html(distance_km)} км\n"

    if price is not None:
        ai_summary += f"💰 <b>Стоимость:</b> {escape_html(format_price(price))}\n"

    # ========================================================
    # СОЗДАНИЕ ЗАКАЗА В БД
    # ========================================================
    try:
        request_id = await create_request(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            raw_text=text,
            ai_summary=ai_summary,
            distance_km=distance_km,
            price=price
        )
    except Exception as error:
        print("❌ ОШИБКА СОЗДАНИЯ ЗАЯВКИ:", repr(error))
        await send_html_message(
            message.bot,
            message.chat.id,
            "❌ Не удалось создать заявку.\nПопробуйте отправить её ещё раз.",
            reply_markup=client_menu()
        )
        return

    print("=" * 60)
    print("ЗАЯВКА СОЗДАНА НОМЕР:", request_id)
    print("=" * 60)

    client_name = f"@{message.from_user.username}" if message.from_user.username else (message.from_user.first_name or "не указан")

    # ========================================================
    # КАРТОЧКА АДМИНИСТРАТОРУ
    # ========================================================
    admin_text = (
        f"🚕 <b>НОВАЯ ЗАЯВКА №{request_id}</b>\n\n"
        f"👤 <b>Клиент:</b> {escape_html(client_name)}\n"
        f"🆔 <b>ID:</b> {escape_html(message.from_user.id)}\n"
        f"📞 <b>Телефон:</b> не указан\n\n"
        f"{ai_summary}\n"
        f"📝 <b>Сообщение клиента:</b>\n"
        f"{escape_html(text)}"
    )

    try:
        admin_message = await send_html_message(message.bot, get_admin_id(), admin_text)
        await save_admin_message_id(request_id, admin_message.message_id)

        from app.handlers.admin import order_keyboard
        req_obj = await get_request(request_id)
        if req_obj:
            await admin_message.edit_reply_markup(reply_markup=order_keyboard(req_obj))
    except Exception as error:
        print("❌ ОШИБКА КАРТОЧКИ АДМИНУ:", repr(error))

    # ========================================================
    # ЗАКАЗ В ГРУППУ ВОДИТЕЛЕЙ
    # ========================================================
    driver_text = (
        f"🚕 <b>НОВЫЙ ЗАКАЗ №{request_id}</b>\n\n"
        f"📍 <b>Откуда:</b> {escape_html(from_place)}\n"
        f"🏁 <b>Куда:</b> {escape_html(to_place)}\n"
        f"{trip_type}\n"
        f"📅 <b>Дата:</b> {escape_html(date)}\n"
        f"🕐 <b>Время:</b> {escape_html(time)}\n"
        f"👥 <b>Пассажиров:</b> {escape_html(passengers)}\n"
    )

    if distance_km is not None:
        driver_text += f"📏 <b>Расстояние:</b> {escape_html(distance_km)} км\n"

    if price is not None:
        driver_text += f"💰 <b>Стоимость:</b> {escape_html(format_price(price))}\n"

    try:
        await send_html_message(
            message.bot,
            get_drivers_chat_id(),
            driver_text,
            reply_markup=drivers_order_keyboard(request_id)
        )
        print("✅ ЗАКАЗ ОТПРАВЛЕН В ГРУППУ ВОДИТЕЛЕЙ")
    except Exception as error:
        print("❌ ОШИБКА ОТПРАВКИ ВОДИТЕЛЯМ:", repr(error))

    # ========================================================
    # ОТВЕТ КЛИЕНТУ
    # ========================================================
    client_result = (
        "✅ <b>Заявка принята</b>\n\n"
        f"🚕 <b>Номер заказа:</b> №{request_id}\n\n"
        f"{ai_summary}\n\n"
        "📞 <b>Теперь отправьте номер телефона.</b>\n"
        "Нажмите кнопку ниже или отправьте номер обычным сообщением."
    )

    phone_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📞 Отправить номер телефона",
                    request_contact=True
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await send_html_message(
        message.bot,
        message.chat.id,
        client_result,
        reply_markup=phone_keyboard
    )
    print("=" * 60)
    print("ОБРАБОТКА ЗАЯВКИ ЗАВЕРШЕНА:", request_id)
    print("=" * 60)