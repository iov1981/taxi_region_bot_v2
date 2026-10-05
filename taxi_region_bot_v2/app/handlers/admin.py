from aiogram import Router, F

from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from app.config import get_admin_id

from app.db import (
    get_request,
    get_last_request,
    get_active_requests,
    get_driver_requests,
    complete_request,
    cancel_request,
    get_order_history,
    get_tariff_settings,
    set_city_enabled,
    set_intercity_enabled
)


router = Router()

print("admin.py загружен")


# ============================================================
# СТАТУС ЗАКАЗА
# ============================================================

def get_status_text(status):

    if status == "new":
        return "🟢 Новый"

    if status == "taken":
        return "🔵 В работе"

    if status == "done":
        return "✅ Выполнен"

    if status == "cancelled":
        return "❌ Отменён"

    return status


# ============================================================
# ВОДИТЕЛЬ
# ============================================================

def get_driver_text(request):

    if not request["driver_id"]:
        return "—"

    if request["driver_username"]:
        return f"@{request['driver_username']}"

    return request["driver_first_name"] or "водитель"


# ============================================================
# КЛАВИАТУРА КАРТОЧКИ ЗАКАЗА
# ============================================================

def order_keyboard(request):

    request_id = request["id"]

    buttons = [
        [
            InlineKeyboardButton(
                text="📞 Телефон",
                callback_data=f"order_phone:{request_id}"
            ),
            InlineKeyboardButton(
                text="🚕 Водители",
                callback_data=f"order_drivers:{request_id}"
            )
        ]
    ]

    if request["status"] == "new":

        buttons.append(
            [
                InlineKeyboardButton(
                    text="❌ Отменить заказ",
                    callback_data=f"cancel:{request_id}"
                )
            ]
        )

    elif request["status"] == "taken":

        buttons.append(
            [
                InlineKeyboardButton(
                    text="✅ Завершить заказ",
                    callback_data=f"complete:{request_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=f"cancel:{request_id}"
                )
            ]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


# ============================================================
# КЛАВИАТУРА ТАРИФОВ
# ============================================================

async def tariff_keyboard():

    settings = await get_tariff_settings()

    city_status = (
        "🟢 ВКЛ"
        if settings["city_enabled"]
        else "🔴 ВЫКЛ"
    )

    intercity_status = (
        "🟢 ВКЛ"
        if settings["intercity_enabled"]
        else "🔴 ВЫКЛ"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🏙 Город: {city_status}",
                    callback_data="tariff:city"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🛣 Межгород: {intercity_status}",
                    callback_data="tariff:intercity"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="tariff:refresh"
                )
            ]
        ]
    )

    return keyboard


# ============================================================
# УПРАВЛЕНИЕ ТАРИФАМИ
# ============================================================

@router.message(
    F.text == "⚙️ Управление тарифами"
)
async def tariff_settings(message: Message):

    if message.from_user.id != get_admin_id():
        return

    settings = await get_tariff_settings()

    city_status = (
        "🟢 ВКЛ"
        if settings["city_enabled"]
        else "🔴 ВЫКЛ"
    )

    intercity_status = (
        "🟢 ВКЛ"
        if settings["intercity_enabled"]
        else "🔴 ВЫКЛ"
    )

    await message.answer(
        "⚙️ <b>УПРАВЛЕНИЕ ТАРИФАМИ</b>\n\n"
        f"🏙 Город: {city_status}\n"
        f"🛣 Межгород: {intercity_status}\n\n"
        "Нажмите на тариф, чтобы включить "
        "или выключить его.",
        reply_markup=await tariff_keyboard(),
        parse_mode="HTML"
    )


# ============================================================
# ПЕРЕКЛЮЧЕНИЕ ГОРОДА
# ============================================================

@router.callback_query(
    F.data == "tariff:city"
)
async def toggle_city_tariff(
        callback: CallbackQuery
):

    if callback.from_user.id != get_admin_id():

        await callback.answer(
            "❌ Только администратор.",
            show_alert=True
        )

        return

    settings = await get_tariff_settings()

    new_value = not settings["city_enabled"]

    await set_city_enabled(new_value)

    status = (
        "включён 🟢"
        if new_value
        else "выключен 🔴"
    )

    await callback.message.edit_text(
        "⚙️ <b>УПРАВЛЕНИЕ ТАРИФАМИ</b>\n\n"
        f"🏙 Город: "
        f"{'🟢 ВКЛ' if new_value else '🔴 ВЫКЛ'}\n"
        f"🛣 Межгород: "
        f"{'🟢 ВКЛ' if settings['intercity_enabled'] else '🔴 ВЫКЛ'}\n\n"
        f"🏙 Городской тариф {status}.",
        reply_markup=await tariff_keyboard(),
        parse_mode="HTML"
    )

    await callback.answer(
        f"🏙 Городской тариф {status}"
    )


# ============================================================
# ПЕРЕКЛЮЧЕНИЕ МЕЖГОРОДА
# ============================================================

@router.callback_query(
    F.data == "tariff:intercity"
)
async def toggle_intercity_tariff(
        callback: CallbackQuery
):

    if callback.from_user.id != get_admin_id():

        await callback.answer(
            "❌ Только администратор.",
            show_alert=True
        )

        return

    settings = await get_tariff_settings()

    new_value = not settings["intercity_enabled"]

    await set_intercity_enabled(new_value)

    status = (
        "включён 🟢"
        if new_value
        else "выключен 🔴"
    )

    await callback.message.edit_text(
        "⚙️ <b>УПРАВЛЕНИЕ ТАРИФАМИ</b>\n\n"
        f"🏙 Город: "
        f"{'🟢 ВКЛ' if settings['city_enabled'] else '🔴 ВЫКЛ'}\n"
        f"🛣 Межгород: "
        f"{'🟢 ВКЛ' if new_value else '🔴 ВЫКЛ'}\n\n"
        f"🛣 Межгородской тариф {status}.",
        reply_markup=await tariff_keyboard(),
        parse_mode="HTML"
    )

    await callback.answer(
        f"🛣 Межгородской тариф {status}"
    )


# ============================================================
# ОБНОВИТЬ ТАРИФЫ
# ============================================================

@router.callback_query(
    F.data == "tariff:refresh"
)
async def refresh_tariffs(
        callback: CallbackQuery
):

    if callback.from_user.id != get_admin_id():

        await callback.answer(
            "❌ Только администратор.",
            show_alert=True
        )

        return

    settings = await get_tariff_settings()

    city_status = (
        "🟢 ВКЛ"
        if settings["city_enabled"]
        else "🔴 ВЫКЛ"
    )

    intercity_status = (
        "🟢 ВКЛ"
        if settings["intercity_enabled"]
        else "🔴 ВЫКЛ"
    )

    await callback.message.edit_text(
        "⚙️ <b>УПРАВЛЕНИЕ ТАРИФАМИ</b>\n\n"
        f"🏙 Город: {city_status}\n"
        f"🛣 Межгород: {intercity_status}\n\n"
        "Нажмите на тариф, чтобы включить "
        "или выключить его.",
        reply_markup=await tariff_keyboard(),
        parse_mode="HTML"
    )

    await callback.answer(
        "🔄 Настройки обновлены"
    )


# ============================================================
# ПОКАЗАТЬ ТЕЛЕФОН
# ============================================================

@router.callback_query(
    F.data.startswith("order_phone:")
)
async def order_phone(
        callback: CallbackQuery
):

    if callback.from_user.id != get_admin_id():

        await callback.answer(
            "❌ Только администратор.",
            show_alert=True
        )

        return

    try:

        request_id = int(
            callback.data.split(":")[1]
        )

    except (ValueError, IndexError):

        await callback.answer(
            "❌ Неверный номер заказа.",
            show_alert=True
        )

        return

    request = await get_request(
        request_id
    )

    if not request:

        await callback.answer(
            "❌ Заказ не найден.",
            show_alert=True
        )

        return

    phone = (
        request["phone"]
        or "не указан"
    )

    await callback.answer(
        f"📞 Телефон: {phone}",
        show_alert=True
    )


# ============================================================
# ПОКАЗАТЬ ВОДИТЕЛЕЙ
# ============================================================

@router.callback_query(
    F.data.startswith("order_drivers:")
)
async def order_drivers(
        callback: CallbackQuery
):

    if callback.from_user.id != get_admin_id():

        await callback.answer(
            "❌ Только администратор.",
            show_alert=True
        )

        return

    try:

        request_id = int(
            callback.data.split(":")[1]
        )

    except (ValueError, IndexError):

        await callback.answer(
            "❌ Неверный номер заказа.",
            show_alert=True
        )

        return

    request = await get_request(
        request_id
    )

    if not request:

        await callback.answer(
            "❌ Заказ не найден.",
            show_alert=True
        )

        return

    drivers = await get_driver_requests(
        request_id
    )

    if request["status"] == "taken":

        driver_name = get_driver_text(
            request
        )

        await callback.answer(
            f"🔵 Заказ уже у водителя: {driver_name}",
            show_alert=True
        )

        return

    if not drivers:

        await callback.answer(
            "🚕 Пока никто из водителей не предложил себя.",
            show_alert=True
        )

        return

    buttons = []

    for driver in drivers:

        if driver["driver_username"]:

            driver_name = (
                f"@{driver['driver_username']}"
            )

        else:

            driver_name = (
                driver["driver_first_name"]
                or "водитель"
            )

        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"✅ {driver_name}",
                    callback_data=(
                        f"assign:{request_id}:"
                        f"{driver['driver_id']}"
                    )
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="🔄 Обновить список",
                callback_data=(
                    f"order_drivers:{request_id}"
                )
            )
        ]
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons
    )

    text = (
        f"🚕 <b>ВОДИТЕЛИ НА ЗАКАЗ №{request_id}</b>\n\n"
        "Водители, которые написали «БЕРУ»:\n\n"
    )

    for index, driver in enumerate(
        drivers,
        start=1
    ):

        if driver["driver_username"]:

            driver_name = (
                f"@{driver['driver_username']}"
            )

        else:

            driver_name = (
                driver["driver_first_name"]
                or "водитель"
            )

        text += (
            f"{index}. {driver_name}\n"
            f"   🆔 ID: {driver['driver_id']}\n\n"
        )

    text += (
        "👇 Нажмите на водителя, "
        "которого хотите назначить."
    )

    await callback.message.answer(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# ============================================================
# ПОСЛЕДНЯЯ ЗАЯВКА
# ============================================================

@router.message(
    F.text == "📋 Последняя заявка"
)
async def last_request(message: Message):

    if message.from_user.id != get_admin_id():
        return

    request = await get_last_request()

    if not request:

        await message.answer(
            "📋 Заявок пока нет."
        )

        return

    status_text = get_status_text(
        request["status"]
    )

    driver_text = get_driver_text(
        request
    )

    phone = (
        request["phone"]
        or "не указан"
    )

    text = (
        f"🚕 <b>ЗАЯВКА №{request['id']}</b>\n\n"
        f"👤 Клиент: "
        f"{request['first_name'] or 'клиент'}\n"
        f"🆔 ID клиента: "
        f"{request['telegram_id']}\n\n"
        f"{request['ai_summary']}\n\n"
        f"📞 Телефон: {phone}\n"
        f"📊 Статус: {status_text}\n"
        f"🚕 Водитель: {driver_text}\n\n"
        f"📝 Сообщение клиента:\n"
        f"{request['raw_text']}"
    )

    await message.answer(
        text,
        reply_markup=order_keyboard(request),
        parse_mode="HTML"
    )


# ============================================================
# АКТИВНЫЕ ЗАКАЗЫ
# ============================================================

@router.message(
    F.text == "📋 Активные заказы"
)
async def active_requests(message: Message):

    if message.from_user.id != get_admin_id():
        return

    if message.chat.type != "private":

        print(
            "Попытка открыть активные заказы "
            "не в личном чате администратора.",
            "CHAT ID:",
            message.chat.id,
            "CHAT TYPE:",
            message.chat.type
        )

        return

    requests = await get_active_requests()

    if not requests:

        await message.answer(
            "📋 Активных заказов нет."
        )

        return

    await message.answer(
        f"📋 <b>АКТИВНЫЕ ЗАКАЗЫ: {len(requests)}</b>",
        parse_mode="HTML"
    )

    for request in requests:

        status_text = get_status_text(
            request["status"]
        )

        driver_text = get_driver_text(
            request
        )

        phone = (
            request["phone"]
            or "не указан"
        )

        text = (
            f"🚕 <b>ЗАКАЗ №{request['id']}</b>\n\n"
            f"{request['ai_summary']}\n\n"
            f"📞 Телефон: {phone}\n"
            f"📊 Статус: {status_text}\n"
            f"🚕 Водитель: {driver_text}\n\n"
            f"📝 Клиент:\n"
            f"{request['raw_text']}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"🚕 Открыть заказ №{request['id']}",
                        callback_data=(
                            f"active_order:{request['id']}"
                        )
                    )
                ]
            ]
        )

        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )


# ============================================================
# ОТКРЫТЬ АКТИВНЫЙ ЗАКАЗ
# ============================================================

@router.callback_query(
    F.data.startswith("active_order:")
)
async def active_order(
        callback: CallbackQuery
):

    if callback.from_user.id != get_admin_id():

        await callback.answer(
            "❌ Только администратор.",
            show_alert=True
        )

        return

    try:

        request_id = int(
            callback.data.split(":")[1]
        )

    except (ValueError, IndexError):

        await callback.answer(
            "❌ Неверный номер заказа.",
            show_alert=True
        )

        return

    request = await get_request(
        request_id
    )

    if not request:

        await callback.answer(
            "❌ Заказ не найден.",
            show_alert=True
        )

        return

    if request["status"] not in ("new", "taken"):

        await callback.answer(
            "ℹ️ Этот заказ уже не активен.",
            show_alert=True
        )

        return

    status_text = get_status_text(
        request["status"]
    )

    driver_text = get_driver_text(
        request
    )

    phone = (
        request["phone"]
        or "не указан"
    )

    text = (
        f"🚕 <b>ЗАКАЗ №{request['id']}</b>\n\n"
        f"{request['ai_summary']}\n\n"
        f"📞 Телефон: {phone}\n"
        f"📊 Статус: {status_text}\n"
        f"🚕 Водитель: {driver_text}\n\n"
        f"📝 Клиент:\n"
        f"{request['raw_text']}"
    )

    await callback.message.answer(
        text,
        reply_markup=order_keyboard(request),
        parse_mode="HTML"
    )

    await callback.answer()


# ============================================================
# ИСТОРИЯ ЗАКАЗОВ
# ============================================================

@router.message(
    F.text == "📚 История заказов"
)
async def order_history(message: Message):

    if message.from_user.id != get_admin_id():
        return

    requests = await get_order_history(
        limit=20
    )

    if not requests:

        await message.answer(
            "📚 История заказов пока пуста."
        )

        return

    # ========================================================
    # СОРТИРОВКА ИСТОРИИ
    # ========================================================
    #
    # Самый НОВЫЙ заказ должен быть сверху.
    #
    # Например:
    #
    # №5
    # №4
    # №3
    # №2
    # №1
    #
    # Сортируем именно по ID заказа.
    # Чем больше ID — тем новее заказ.
    #
    # Это дополнительно гарантирует правильный порядок,
    # даже если функция get_order_history() вернула
    # записи в другом порядке.
    # ========================================================

    requests = sorted(
        requests,
        key=lambda request: request["id"],
        reverse=True
    )

    await message.answer(
        f"📚 <b>ИСТОРИЯ ЗАКАЗОВ: {len(requests)}</b>",
        parse_mode="HTML"
    )

    for request in requests:

        status_text = get_status_text(
            request["status"]
        )

        driver_text = get_driver_text(
            request
        )

        text = (
            f"🚕 <b>ЗАКАЗ №{request['id']}</b>\n\n"
            f"📊 Статус: {status_text}\n"
            f"{request['ai_summary']}\n"
            f"🚕 Водитель: {driver_text}\n"
            f"🕐 Создан: {request['created_at']}"
        )

        await message.answer(
            text,
            parse_mode="HTML"
        )


# ============================================================
# ЗАВЕРШИТЬ ЗАКАЗ
# ============================================================

@router.callback_query(
    F.data.startswith("complete:")
)
async def complete_order(
        callback: CallbackQuery
):

    if callback.from_user.id != get_admin_id():

        await callback.answer(
            "❌ Только администратор.",
            show_alert=True
        )

        return

    try:

        request_id = int(
            callback.data.split(":")[1]
        )

    except (ValueError, IndexError):

        await callback.answer(
            "❌ Неверный номер заказа.",
            show_alert=True
        )

        return

    request = await get_request(
        request_id
    )

    if not request:

        await callback.answer(
            "❌ Заказ не найден.",
            show_alert=True
        )

        return

    if request["status"] != "taken":

        await callback.answer(
            "⚠️ Этот заказ ещё не находится в работе.",
            show_alert=True
        )

        return

    await complete_request(
        request_id
    )

    await callback.message.edit_text(
        f"🚕 <b>ЗАКАЗ №{request_id}</b>\n\n"
        f"{request['ai_summary']}\n\n"
        f"📞 Телефон: "
        f"{request['phone'] or 'не указан'}\n"
        f"🚕 Водитель: "
        f"{get_driver_text(request)}\n\n"
        f"✅ <b>ЗАКАЗ ВЫПОЛНЕН</b>",
        parse_mode="HTML"
    )

    await callback.answer(
        "✅ Заказ завершён"
    )


# ============================================================
# ОТМЕНИТЬ ЗАКАЗ
# ============================================================

@router.callback_query(
    F.data.startswith("cancel:")
)
async def cancel_order(
        callback: CallbackQuery
):

    if callback.from_user.id != get_admin_id():

        await callback.answer(
            "❌ Только администратор.",
            show_alert=True
        )

        return

    try:

        request_id = int(
            callback.data.split(":")[1]
        )

    except (ValueError, IndexError):

        await callback.answer(
            "❌ Неверный номер заказа.",
            show_alert=True
        )

        return

    request = await get_request(
        request_id
    )

    if not request:

        await callback.answer(
            "❌ Заказ не найден.",
            show_alert=True
        )

        return

    if request["status"] == "done":

        await callback.answer(
            "⚠️ Заказ уже выполнен.",
            show_alert=True
        )

        return

    if request["status"] == "cancelled":

        await callback.answer(
            "⚠️ Заказ уже отменён.",
            show_alert=True
        )

        return

    await cancel_request(
        request_id
    )

    await callback.message.edit_text(
        f"🚕 <b>ЗАКАЗ №{request_id}</b>\n\n"
        f"{request['ai_summary']}\n\n"
        f"📞 Телефон: "
        f"{request['phone'] or 'не указан'}\n"
        f"🚕 Водитель: "
        f"{get_driver_text(request)}\n\n"
        f"❌ <b>ЗАКАЗ ОТМЕНЁН</b>",
        parse_mode="HTML"
    )

    await callback.answer(
        "❌ Заказ отменён"
    )

    if request["driver_id"]:

        try:

            await callback.message.bot.send_message(
                request["driver_id"],
                f"❌ <b>ЗАКАЗ №{request_id} ОТМЕНЁН</b>\n\n"
                f"{request['ai_summary']}",
                parse_mode="HTML"
            )

        except Exception as error:

            print(
                "ОШИБКА УВЕДОМЛЕНИЯ ВОДИТЕЛЯ:",
                repr(error)
            )