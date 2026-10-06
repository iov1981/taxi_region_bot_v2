
import html
from html.parser import HTMLParser

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

from app.services.ai_parser import parse_request
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
        super().__init__(
            convert_charrefs=False
        )

        self.errors = []
        self.open_tags = []

    def handle_starttag(self, tag, attrs):

        tag = tag.lower()

        if tag not in self.ALLOWED_TAGS:

            self.errors.append(
                f"Недопустимый HTML-тег: <{tag}>"
            )

            return

        self.open_tags.append(tag)

    def handle_startendtag(self, tag, attrs):

        tag = tag.lower()

        if tag not in self.ALLOWED_TAGS:

            self.errors.append(
                f"Недопустимый HTML-тег: <{tag}/>"
            )

    def handle_endtag(self, tag):

        tag = tag.lower()

        if tag not in self.ALLOWED_TAGS:

            self.errors.append(
                f"Недопустимый закрывающий тег: </{tag}>"
            )

            return

        if not self.open_tags:

            self.errors.append(
                f"Лишний закрывающий тег: </{tag}>"
            )

            return

        if self.open_tags[-1] != tag:

            self.errors.append(
                "Нарушена вложенность HTML: "
                f"ожидался </{self.open_tags[-1]}>, "
                f"получен </{tag}>"
            )

            return

        self.open_tags.pop()

    def handle_comment(self, data):

        self.errors.append(
            "HTML-комментарии запрещены."
        )


def validate_html(text: str) -> tuple[bool, list[str]]:

    if not isinstance(text, str):

        return False, [
            "Текст сообщения не является строкой."
        ]

    parser = TelegramHTMLValidator()

    try:

        parser.feed(text)
        parser.close()

    except Exception as error:

        parser.errors.append(
            f"Ошибка HTML-парсера: {error}"
        )

    if parser.open_tags:

        parser.errors.append(
            "Не закрыты HTML-теги: "
            + ", ".join(
                f"<{tag}>"
                for tag in parser.open_tags
            )
        )

    return (
        len(parser.errors) == 0,
        parser.errors
    )


def escape_html(value) -> str:

    if value is None:
        return ""

    return html.escape(
        str(value),
        quote=False
    )


async def send_html_message(
        bot,
        chat_id,
        text,
        **kwargs
):

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

        print(
            "HTML:",
            error
        )

    print()
    print("ТЕКСТ С ОШИБКОЙ:")
    print(text)
    print("=" * 60)

    safe_text = html.escape(
        text,
        quote=False
    )

    return await bot.send_message(
        chat_id,
        safe_text,
        **kwargs
    )


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

def drivers_order_keyboard(request_id):

    builder = InlineKeyboardBuilder()

    builder.button(
        text="🟢 БЕРУ ЗАКАЗ",
        callback_data=f"driver_wants:{request_id}"
    )

    return builder.as_markup()


# ============================================================
# ОБНОВЛЕНИЕ КАРТОЧКИ АДМИНИСТРАТОРА
# ============================================================

async def update_admin_order_card(
        message: Message,
        request: dict,
        phone: str
):

    try:

        admin_message_id = request["admin_message_id"]

        if not admin_message_id:

            print(
                "⚠️ У заявки нет admin_message_id"
            )

            return

        from app.handlers.admin import order_keyboard

        if message.from_user.username:

            client_name = (
                f"@{message.from_user.username}"
            )

        else:

            client_name = (
                message.from_user.first_name
                or "не указан"
            )

        updated_admin_text = (
            f"🚕 <b>НОВАЯ ЗАЯВКА №{request['id']}</b>\n\n"
            f"👤 <b>Клиент:</b> "
            f"{escape_html(client_name)}\n"
            f"🆔 <b>ID:</b> "
            f"{escape_html(message.from_user.id)}\n"
            f"📞 <b>Телефон:</b> "
            f"{escape_html(phone)}\n\n"
            f"{request['ai_summary']}\n"
            f"📝 <b>Сообщение клиента:</b>\n"
            f"{escape_html(request['raw_text'])}"
        )

        valid, errors = validate_html(
            updated_admin_text
        )

        if not valid:

            print()
            print(
                "❌ HTML карточки администратора "
                "не прошёл проверку."
            )

            for error in errors:

                print(
                    "HTML:",
                    error
                )

            return

        await message.bot.edit_message_text(
            chat_id=get_admin_id(),
            message_id=admin_message_id,
            text=updated_admin_text,
            parse_mode="HTML",
            reply_markup=order_keyboard(request)
        )

        print()
        print(
            "✅ КАРТОЧКА АДМИНА ОБНОВЛЕНА ТЕЛЕФОНОМ"
        )

        print(
            "REQUEST ID:",
            request["id"]
        )

        print(
            "PHONE:",
            phone
        )

    except Exception as error:

        print()
        print(
            "❌ ОШИБКА ОБНОВЛЕНИЯ КАРТОЧКИ АДМИНА:"
        )

        print(
            type(error).__name__,
            repr(error)
        )


# ============================================================
# СОХРАНЕНИЕ ТЕЛЕФОНА
# ============================================================

async def process_phone(
        message: Message,
        phone: str
):

    phone = phone.strip()

    print()
    print("=" * 60)
    print("ПОЛУЧЕН ТЕЛЕФОН КЛИЕНТА")
    print("=" * 60)

    print(
        "USER ID:",
        message.from_user.id
    )

    print(
        "PHONE:",
        phone
    )

    print("=" * 60)

    try:

        request = await save_phone(
            message.from_user.id,
            phone
        )

        if not request:

            await message.answer(
                "⚠️ У вас пока нет активной заявки.\n\n"
                "Сначала отправьте маршрут поездки.",
                reply_markup=client_menu()
            )

            return True

        request_id = request["id"]

        print(
            "ЗАЯВКА ДЛЯ ТЕЛЕФОНА:",
            request_id
        )

        await update_admin_order_card(
            message,
            request,
            phone
        )

        await send_html_message(
            message.bot,
            message.chat.id,
            "📞 <b>Телефон сохранён.</b>\n\n"
            "Администратор увидит его в заявке.",
            reply_markup=client_menu()
        )

        print(
            "✅ ТЕЛЕФОН СОХРАНЁН "
            f"ДЛЯ ЗАКАЗА №{request_id}"
        )

        return True

    except Exception as error:

        print()
        print(
            "❌ ОШИБКА СОХРАНЕНИЯ ТЕЛЕФОНА:"
        )

        print(
            type(error).__name__,
            repr(error)
        )

        await message.answer(
            "❌ Не удалось сохранить номер телефона.\n"
            "Попробуйте отправить его ещё раз.",
            reply_markup=client_menu()
        )

        return True


# ============================================================
# ОБРАБОТКА СООБЩЕНИЯ КЛИЕНТА
# ============================================================

@router.message(
    F.chat.id > 0,
    F.text | F.contact
)
async def handle_message(message: Message):

    # ========================================================
    # TELEGRAM-КОНТАКТ
    # ========================================================

    if message.contact:

        phone = message.contact.phone_number.strip()

        print()
        print("=" * 60)
        print("ПОЛУЧЕН КОНТАКТ КЛИЕНТА")
        print("=" * 60)

        print(
            "USER ID:",
            message.from_user.id
        )

        print(
            "CONTACT USER ID:",
            message.contact.user_id
        )

        print(
            "PHONE:",
            phone
        )

        print("=" * 60)

        if (
            message.contact.user_id is not None
            and message.contact.user_id != message.from_user.id
        ):

            await message.answer(
                "⚠️ Пожалуйста, отправьте свой номер телефона.",
                reply_markup=client_menu()
            )

            return

        await process_phone(
            message,
            phone
        )

        return

    # ========================================================
    # ОБЫЧНЫЙ ТЕКСТ
    # ========================================================

    text = (message.text or "").strip()

    if not text:
        return

    # ========================================================
    # ЗАЩИТА ОТ СЛУЖЕБНЫХ СООБЩЕНИЙ
    # ========================================================

    if is_internal_message(text):

        print()
        print("=" * 60)
        print("⚠️ СЛУЖЕБНОЕ СООБЩЕНИЕ")
        print("=" * 60)

        print(
            "USER ID:",
            message.from_user.id
        )

        print(
            "TEXT:",
            text
        )

        print(
            "СООБЩЕНИЕ НЕ БУДЕТ "
            "ОБРАБОТАНО КАК ЗАЯВКА."
        )

        print("=" * 60)

        return

    # ========================================================
    # ЛОГИРОВАНИЕ
    # ========================================================

    print()
    print("=" * 60)
    print("ПОЛУЧЕНО СООБЩЕНИЕ ОТ КЛИЕНТА")
    print("=" * 60)

    print(
        "USER ID:",
        message.from_user.id
    )

    print(
        "USERNAME:",
        message.from_user.username
    )

    print(
        "NAME:",
        message.from_user.first_name
    )

    print(
        "TEXT:",
        text
    )

    print("=" * 60)

    # ========================================================
    # ПРОВЕРКА ТЕЛЕФОНА
    # ========================================================

    phone_text = (
        text
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    if phone_text.startswith("8") and len(phone_text) == 11:

        phone_text = (
            "+7" + phone_text[1:]
        )

    if (
        phone_text.startswith("+7")
        and phone_text[1:].isdigit()
        and len(phone_text) == 12
    ):

        await process_phone(
            message,
            phone_text
        )

        return

    # ========================================================
    # РАЗБОР ЗАЯВКИ
    # ========================================================

    try:

        parsed = await parse_request(
            text
        )

    except Exception as error:

        print(
            "ОШИБКА ПАРСЕРА:",
            repr(error)
        )

        await send_html_message(
            message.bot,
            message.chat.id,
            "❌ <b>Не удалось разобрать заявку.</b>\n\n"
            "Пример:\n"
            "Пенза — Воробьевка, "
            "2 человека, завтра утром",
            reply_markup=client_menu()
        )

        return

    # ========================================================
    # ДАННЫЕ ИЗ ПАРСЕРА
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

    if (
        route_from != "не определено"
        and route_to != "не определено"
    ):

        print()
        print("=" * 60)
        print("ПОСТРОЕНИЕ МАРШРУТА")
        print("=" * 60)

        print(
            "ОТКУДА:",
            route_from
        )

        print(
            "КУДА:",
            route_to
        )

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
                    "РАССТОЯНИЕ НЕ ОПРЕДЕЛЕНО"
                )

        except Exception as error:

            print(
                "ОШИБКА МАРШРУТА:",
                repr(error)
            )

    # ========================================================
    # КРАТКАЯ ИНФОРМАЦИЯ О ЗАКАЗЕ
    # ========================================================

    ai_summary = (
        f"📍 <b>Откуда:</b> "
        f"{escape_html(from_place)}\n"
        f"🏁 <b>Куда:</b> "
        f"{escape_html(to_place)}\n"
        f"{trip_type}\n"
        f"📅 <b>Дата:</b> "
        f"{escape_html(date)}\n"
        f"🕐 <b>Время:</b> "
        f"{escape_html(time)}\n"
        f"👥 <b>Пассажиров:</b> "
        f"{escape_html(passengers)}\n"
    )

    if distance_km is not None:

        ai_summary += (
            f"📏 <b>Расстояние:</b> "
            f"{escape_html(distance_km)} км\n"
        )

    if price is not None:

        ai_summary += (
            f"💰 <b>Стоимость:</b> "
            f"{escape_html(format_price(price))}\n"
        )

    # ========================================================
    # СОЗДАНИЕ ЗАКАЗА
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

        print()
        print(
            "❌ ОШИБКА СОЗДАНИЯ ЗАЯВКИ:"
        )

        print(
            type(error).__name__,
            repr(error)
        )

        await send_html_message(
            message.bot,
            message.chat.id,
            "❌ Не удалось создать заявку.\n\n"
            "Попробуйте отправить её ещё раз.",
            reply_markup=client_menu()
        )

        return

    print()
    print("=" * 60)
    print("ЗАЯВКА СОЗДАНА")
    print(
        "НОМЕР:",
        request_id
    )
    print("=" * 60)

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
        f"🚕 <b>НОВАЯ ЗАЯВКА №{request_id}</b>\n\n"
        f"👤 <b>Клиент:</b> "
        f"{escape_html(client_name)}\n"
        f"🆔 <b>ID:</b> "
        f"{escape_html(message.from_user.id)}\n"
        f"📞 <b>Телефон:</b> не указан\n\n"
        f"{ai_summary}\n"
        f"📝 <b>Сообщение клиента:</b>\n"
        f"{escape_html(text)}"
    )

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

    print(
        "КЛИЕНТ:",
        client_name
    )

    print("=" * 60)

    try:

        admin_message = await send_html_message(
            message.bot,
            get_admin_id(),
            admin_text
        )

        print(
            "✅ КАРТОЧКА АДМИНУ ОТПРАВЛЕНА"
        )

        try:

            await save_admin_message_id(
                request_id,
                admin_message.message_id
            )

            print(
                "✅ admin_message_id сохранён."
            )

        except Exception as error:

            print(
                "ОШИБКА СОХРАНЕНИЯ "
                "admin_message_id:",
                repr(error)
            )

        try:

            from app.handlers.admin import order_keyboard

            request = await get_request(
                request_id
            )

            if request:

                await admin_message.edit_reply_markup(
                    reply_markup=order_keyboard(
                        request
                    )
                )

                print(
                    "✅ КНОПКИ КАРТОЧКИ АДМИНА ДОБАВЛЕНЫ"
                )

        except Exception as error:

            print(
                "ОШИБКА ДОБАВЛЕНИЯ "
                "КНОПОК АДМИНУ:",
                repr(error)
            )

    except Exception as error:

        print()
        print(
            "❌ ОШИБКА ОТПРАВКИ "
            "КАРТОЧКИ АДМИНУ"
        )

        print(
            type(error).__name__,
            repr(error)
        )

    # ========================================================
    # ЗАКАЗ В ГРУППУ ВОДИТЕЛЕЙ
    # ========================================================

    driver_text = (
        f"🚕 <b>НОВЫЙ ЗАКАЗ №{request_id}</b>\n\n"
        f"📍 <b>Откуда:</b> "
        f"{escape_html(from_place)}\n"
        f"🏁 <b>Куда:</b> "
        f"{escape_html(to_place)}\n"
        f"{trip_type}\n"
        f"📅 <b>Дата:</b> "
        f"{escape_html(date)}\n"
        f"🕐 <b>Время:</b> "
        f"{escape_html(time)}\n"
        f"👥 <b>Пассажиров:</b> "
        f"{escape_html(passengers)}\n"
    )

    if distance_km is not None:

        driver_text += (
            f"📏 <b>Расстояние:</b> "
            f"{escape_html(distance_km)} км\n"
        )

    if price is not None:

        driver_text += (
            f"💰 <b>Стоимость:</b> "
            f"{escape_html(format_price(price))}\n"
        )

    print()
    print("=" * 60)
    print("ОТПРАВКА ЗАКАЗА ВОДИТЕЛЯМ")
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

        driver_message = await send_html_message(
            message.bot,
            get_drivers_chat_id(),
            driver_text,
            reply_markup=drivers_order_keyboard(
                request_id
            )
        )

        print(
            "✅ ЗАКАЗ ОТПРАВЛЕН "
            "В ГРУППУ ВОДИТЕЛЕЙ"
        )

        print(
            "MESSAGE ID:",
            driver_message.message_id
        )

        print(
            "✅ КНОПКА 🟢 БЕРУ ЗАКАЗ ДОБАВЛЕНА"
        )

    except Exception as error:

        print()
        print(
            "❌ ОШИБКА ОТПРАВКИ "
            "ЗАКАЗА ВОДИТЕЛЯМ"
        )

        print(
            type(error).__name__,
            repr(error)
        )

    # ========================================================
    # ОТВЕТ КЛИЕНТУ
    # ========================================================

    client_result = (
        "✅ <b>Заявка принята</b>\n\n"
        f"🚕 <b>Номер заказа:</b> №{request_id}\n\n"
        f"{ai_summary}\n\n"
        "📞 <b>Теперь отправьте номер телефона.</b>\n"
        "Нажмите кнопку ниже или отправьте номер "
        "обычным сообщением."
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

    print()
    print("=" * 60)
    print("ОБРАБОТКА ЗАЯВКИ ЗАВЕРШЕНА")
    print(
        "НОМЕР ЗАКАЗА:",
        request_id
    )
    print("=" * 60)
    print()
