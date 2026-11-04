from aiogram import Router, F
from aiogram.filters import Command, or_f
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import get_admin_id
from app.db import (
    get_request,
    add_driver_request,
    get_driver_requests,
    assign_driver,
    complete_request,
    cancel_request,
    get_driver_profile,
    save_order_rating,
    get_driver_finances,
    set_order_arrived
)

router = Router()
print("drivers.py загружен")

driver_order_messages = {}


def driver_accept_keyboard(request_id: int, driver_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Принять водителя", callback_data=f"assign:{request_id}:{driver_id}")
    return builder.as_markup()


def driver_action_keyboard(request_id: int, client_id: int, arrived: bool = False) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text="💬 Написать клиенту", url=f"tg://user?id={client_id}")]]
    if not arrived:
        buttons.append([InlineKeyboardButton(text="🚖 Я на месте (ожидаю)", callback_data=f"driver_arrived:{request_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="🏁 Завершить заказ", callback_data=f"driver_finish:{request_id}")])
    buttons.append([InlineKeyboardButton(text="❌ Отменить поездку", callback_data=f"driver_cancel:{request_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def client_rating_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⭐️ 1", callback_data=f"rate:{request_id}:1"),
        InlineKeyboardButton(text="⭐️ 2", callback_data=f"rate:{request_id}:2"),
        InlineKeyboardButton(text="⭐️ 3", callback_data=f"rate:{request_id}:3"),
        InlineKeyboardButton(text="⭐️ 4", callback_data=f"rate:{request_id}:4"),
        InlineKeyboardButton(text="⭐️ 5", callback_data=f"rate:{request_id}:5")
    ]])


# --- БАЛАНС И ЗАРАБОТОК ВОДИТЕЛЯ ---

@router.message(or_f(Command("balance"), F.text == "💼 Мой баланс"))
async def driver_balance_cmd(message: Message):
    driver_id = message.from_user.id
    finances = await get_driver_finances(driver_id)

    today = finances["today"]
    week = finances["week"]
    total = finances["total"]

    if total["orders"] == 0:
        await message.answer(
            "💼 <b>Ваш финансовый баланс</b>\n\n"
            "У вас пока нет выполненных поездок.\n"
            "После первой закрытой заявки здесь отобразится касса, чистый доход и расчёт комиссии.",
            parse_mode="HTML"
        )
        return

    text = (
        "💼 <b>БАЛАНС И ЗАРАБОТОК ВОДИТЕЛЯ</b>\n"
        "──────────────────────\n"
        "🟢 <b>СЕГОДНЯ (ЗА СМЕНУ):</b>\n"
        f"• Выполнено заказов: <b>{today['orders']}</b>\n"
        f"• Касса (общая): <b>{today['revenue']:,} ₽</b>\n"
        f"• Комиссия сервиса: <b>{today['commission']:,} ₽</b>\n"
        f"• Ваш чистый доход: <b>{today['payout']:,} ₽</b>\n\n"
        "📅 <b>ЗА ПОСЛЕДНИЕ 7 ДНЕЙ:</b>\n"
        f"• Заказов: <b>{week['orders']}</b>\n"
        f"• Общая касса: <b>{week['revenue']:,} ₽</b>\n"
        f"• Чистый доход: <b>{week['payout']:,} ₽</b>\n\n"
        "──────────────────────\n"
        f"💳 <b>ДОЛГ ПО КОМИССИИ СЕРВИСА:</b> <b>{total['commission']:,} ₽</b>\n"
        f"<i>(Сумма к переводу диспетчеру за {total['orders']} выполненных заказов)</i>"
    ).replace(",", " ")

    refresh_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔄 Обновить баланс", callback_data="driver_refresh_balance")
    ]])
    await message.answer(text, reply_markup=refresh_kb, parse_mode="HTML")


@router.callback_query(F.data == "driver_refresh_balance")
async def driver_refresh_balance_callback(callback: CallbackQuery):
    finances = await get_driver_finances(callback.from_user.id)
    today = finances["today"]
    week = finances["week"]
    total = finances["total"]

    text = (
        "💼 <b>БАЛАНС И ЗАРАБОТОК ВОДИТЕЛЯ</b>\n"
        "──────────────────────\n"
        "🟢 <b>СЕГОДНЯ (ЗА СМЕНУ):</b>\n"
        f"• Выполнено заказов: <b>{today['orders']}</b>\n"
        f"• Касса (общая): <b>{today['revenue']:,} ₽</b>\n"
        f"• Комиссия сервиса: <b>{today['commission']:,} ₽</b>\n"
        f"• Ваш чистый доход: <b>{today['payout']:,} ₽</b>\n\n"
        "📅 <b>ЗА ПОСЛЕДНИЕ 7 ДНЕЙ:</b>\n"
        f"• Заказов: <b>{week['orders']}</b>\n"
        f"• Общая касса: <b>{week['revenue']:,} ₽</b>\n"
        f"• Чистый доход: <b>{week['payout']:,} ₽</b>\n\n"
        "──────────────────────\n"
        f"💳 <b>ДОЛГ ПО КОМИССИИ СЕРВИСА:</b> <b>{total['commission']:,} ₽</b>\n"
        f"<i>(Сумма к переводу диспетчеру за {total['orders']} выполненных заказов)</i>"
    ).replace(",", " ")

    refresh_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔄 Обновить баланс", callback_data="driver_refresh_balance")
    ]])

    try:
        await callback.message.edit_text(text, reply_markup=refresh_kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("🔄 Баланс обновлён")


# --- ОТКЛИКИ И РАБОТА С ЗАКАЗОМ ---

@router.callback_query(F.data.startswith("driver_wants:"))
async def driver_wants_order(callback: CallbackQuery):
    req_id = int(callback.data.split(":")[1])
    driver_order_messages[req_id] = {
        "chat_id": callback.message.chat.id,
        "message_id": callback.message.message_id
    }

    request = await get_request(req_id)
    if not request or request["status"] != "new":
        await callback.answer("⚠️ Этот заказ уже назначен.", show_alert=True)
        return

    driver_id = callback.from_user.id
    driver_name = f"@{callback.from_user.username}" if callback.from_user.username else (callback.from_user.first_name or "водитель")
    profile = await get_driver_profile(driver_id)
    car_text = profile.get("car_info") if profile and profile.get("car_info") else "авто не указано (/set_car)"
    rating_val = f"{profile['rating']} ⭐️" if profile and profile.get("rating") else "5.0 ⭐️"

    success, result = await add_driver_request(
        req_id, driver_id, callback.from_user.username, callback.from_user.first_name
    )

    if not success:
        await callback.answer("ℹ️ Вы уже предложили себя на этот заказ." if result == "already_waiting" else "⚠️ Заказ уже назначен.", show_alert=True)
        return

    await callback.answer("✅ Отклик отправлен диспетчеру.", show_alert=True)
    admin_text = (
        f"🚕 <b>ВОДИТЕЛЬ ХОЧЕТ ЗАКАЗ №{req_id}</b>\n\n"
        f"👤 <b>Водитель:</b> {driver_name}\n🚗 <b>Авто:</b> {car_text}\n⭐️ <b>Рейтинг:</b> {rating_val}\n🆔 <b>ID:</b> {driver_id}\n\n"
        f"{request['ai_summary']}\n\n📱 <b>Телефон:</b> {request.get('phone') or 'не указан'}"
    )
    await callback.bot.send_message(get_admin_id(), admin_text, parse_mode="HTML", reply_markup=driver_accept_keyboard(req_id, driver_id))


@router.callback_query(F.data.startswith("assign:"))
async def assign_driver_callback(callback: CallbackQuery):
    if callback.from_user.id != get_admin_id():
        return

    parts = callback.data.split(":")
    req_id, driver_id = int(parts[1]), int(parts[2])

    request = await get_request(req_id)
    if not request or request["status"] != "new":
        await callback.answer("⚠️ Заказ уже назначен.", show_alert=True)
        return

    drivers = await get_driver_requests(req_id)
    selected_driver = next((d for d in drivers if d["driver_id"] == driver_id), None)
    if not selected_driver:
        await callback.answer("❌ Водитель не найден.", show_alert=True)
        return

    success = await assign_driver(
        req_id, driver_id, selected_driver["driver_username"], selected_driver["driver_first_name"]
    )
    if not success:
        await callback.answer("⚠️ Заказ уже был назначен.", show_alert=True)
        return

    driver_name = f"@{selected_driver['driver_username']}" if selected_driver["driver_username"] else (selected_driver["driver_first_name"] or "водитель")
    profile = await get_driver_profile(driver_id)
    car_info = profile.get("car_info") if profile and profile.get("car_info") else "уточняется"
    rating_display = f"{profile['rating']} ⭐️" if profile and profile.get("rating") else "5.0 ⭐️"

    await callback.answer("✅ Водитель назначен.", show_alert=True)
    await callback.message.edit_text(
        f"✅ <b>ВОДИТЕЛЬ НАЗНАЧЕН</b>\n\n🚕 <b>Заказ №{req_id}</b>\n👤 Водитель: {driver_name}\n🚗 Авто: {car_info}",
        parse_mode="HTML"
    )

    drv_msg = driver_order_messages.get(req_id)
    if drv_msg:
        try:
            await callback.bot.edit_message_reply_markup(chat_id=drv_msg["chat_id"], message_id=drv_msg["message_id"], reply_markup=None)
            driver_order_messages.pop(req_id, None)
        except Exception:
            pass

    client_id = request.get("telegram_id")
    client_link = f"@{request['username']}" if request.get("username") else f"ID: {client_id}"
    await callback.bot.send_message(
        driver_id,
        f"✅ <b>ВАМ НАЗНАЧЕН ЗАКАЗ №{req_id}</b>\n\n{request['ai_summary']}\n\n👤 <b>Пассажир:</b> {client_link}\n📱 <b>Телефон:</b> {request.get('phone') or 'ожидается...'}\n\nПо прибытии нажмите «🚖 Я на месте»:",
        parse_mode="HTML",
        reply_markup=driver_action_keyboard(req_id, client_id=client_id, arrived=False)
    )

    if client_id:
        try:
            client_buttons = []
            if selected_driver["driver_username"]:
                client_buttons.append([InlineKeyboardButton(text="💬 Написать водителю", url=f"https://t.me/{selected_driver['driver_username']}")])
            client_buttons.append([InlineKeyboardButton(text="❌ Отменить поездку", callback_data=f"client_cancel:{req_id}")])

            await callback.bot.send_message(
                client_id,
                f"🚕 <b>Водитель назначен на заказ №{req_id}!</b>\n\n"
                f"👤 <b>Водитель:</b> {driver_name} ({rating_display})\n"
                f"🚗 <b>Автомобиль:</b> {car_info}\n\n"
                "Машина выехала к вам. Мы сообщим, когда такси подъедет.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=client_buttons)
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("driver_arrived:"))
async def driver_arrived_callback(callback: CallbackQuery):
    req_id = int(callback.data.split(":")[1])
    request = await get_request(req_id)
    if not request or request["driver_id"] != callback.from_user.id:
        return

    await set_order_arrived(req_id)
    await callback.answer("✅ Клиент оповещён о подаче автомобиля!")
    client_id = request.get("telegram_id")

    try:
        await callback.message.edit_reply_markup(reply_markup=driver_action_keyboard(req_id, client_id=client_id, arrived=True))
    except Exception:
        pass

    if client_id:
        try:
            await callback.bot.send_message(
                client_id,
                f"🚖 <b>Такси ожидает вас по заказу №{req_id}!</b>\n"
                "Водитель на месте. Пожалуйста, выходите к автомобилю.",
                parse_mode="HTML"
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("driver_finish:"))
async def driver_finish_order(callback: CallbackQuery):
    req_id = int(callback.data.split(":")[1])
    request = await get_request(req_id)
    if not request or request["driver_id"] != callback.from_user.id or request["status"] == "done":
        await callback.answer("Заказ уже завершён.", show_alert=True)
        return

    calc = await complete_request(req_id)
    await callback.message.edit_text(
        f"🏁 <b>Заказ №{req_id} успешно завершён!</b>\n\n"
        f"💰 <b>Сумма поездки:</b> {calc['price']} ₽\n"
        f"💼 <b>Комиссия диспетчера ({calc['percent']}%):</b> {calc['commission']} ₽\n"
        f"💵 <b>Ваш чистый заработок:</b> {calc['driver_payout']} ₽\n\nСпасибо за работу!",
        parse_mode="HTML"
    )
    await callback.answer("✅ Заказ завершён.")

    if request.get("telegram_id"):
        try:
            await callback.bot.send_message(
                chat_id=request["telegram_id"],
                text=f"🏁 <b>Поездка по заказу №{req_id} завершена.</b>\nПожалуйста, оцените качество поездки:",
                parse_mode="HTML",
                reply_markup=client_rating_keyboard(req_id)
            )
        except Exception:
            pass

    try:
        await callback.bot.send_message(
            chat_id=get_admin_id(),
            text=(
                f"✅ <b>Заказ №{req_id} выполнен водителем.</b>\n\n"
                f"💰 Касса: <b>{calc['price']} ₽</b>\n"
                f"💼 Доход сервиса ({calc['percent']}%): <b>{calc['commission']} ₽</b>\n"
                f"🚕 Начислено водителю: <b>{calc['driver_payout']} ₽</b>"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("rate:"))
async def rate_order_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    req_id, score = int(parts[1]), int(parts[2])
    request = await get_request(req_id)
    if not request or not request.get("driver_id"):
        return

    success = await save_order_rating(req_id, callback.from_user.id, request["driver_id"], score)
    if not success:
        await callback.answer("Вы уже оценили эту поездку.", show_alert=True)
        return

    stars = "⭐️" * score
    await callback.message.edit_text(f"✅ <b>Спасибо за вашу оценку: {stars}!</b>", parse_mode="HTML")
    await callback.answer(f"Оценка {score} принята!")

    try:
        await callback.bot.send_message(
            get_admin_id(), f"⭐️ <b>Клиент оценил заказ №{req_id}:</b> {stars} ({score}/5)", parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("driver_cancel:"))
async def driver_cancel_order(callback: CallbackQuery):
    req_id = int(callback.data.split(":")[1])
    request = await get_request(req_id)
    if not request or request["driver_id"] != callback.from_user.id:
        return

    await cancel_request(req_id)
    await callback.message.edit_text(f"❌ <b>Поездка по заказу №{req_id} отменена вами.</b>", parse_mode="HTML")
    await callback.answer("Поездка отменена.")

    try:
        await callback.bot.send_message(
            get_admin_id(), f"⚠️ <b>Внимание!</b> Водитель отменил поездку по заказу №{req_id}.", parse_mode="HTML"
        )
    except Exception:
        pass