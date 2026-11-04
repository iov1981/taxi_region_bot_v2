import json
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.config import get_admin_id, get_drivers_chat_id
from app.db import (
    create_request,
    get_request,
    cancel_request,
    save_phone,
    get_user_phone,
    get_tariff_settings,
    save_admin_message_id,
    get_ban_info
)
from app.services.parser import parse_order_text
from app.services.route_service import get_route_distance
from app.services.price_service import calculate_price
from app.handlers.drivers import driver_order_messages

router = Router()
print("messages.py загружен")

SEARCH_TIMEOUT_SECONDS = 600


def driver_want_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="🟢 БЕРУ ЗАКАЗ", callback_data=f"driver_wants:{request_id}")
        ]]
    )


def client_cancel_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"client_cancel:{request_id}")
        ]]
    )


# --- ТАЙМАУТ ПОИСКА ---

async def order_search_timeout_task(bot: Bot, request_id: int, delay: int = SEARCH_TIMEOUT_SECONDS):
    await asyncio.sleep(delay)

    req = await get_request(request_id)
    if req and req.get("status") == "new":
        client_id = req["telegram_id"]
        text = (
            f"⏳ <b>Поиск автомобиля по заказу №{request_id} затянулся</b>\n\n"
            "К сожалению, в данный момент все ближайшие водители заняты.\n"
            "Вы хотите продолжить поиск или отменить заказ?"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Продолжить поиск", callback_data=f"client_retry:{request_id}")],
                [InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"client_cancel:{request_id}")]
            ]
        )
        try:
            await bot.send_message(client_id, text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            pass


# --- ДЕЙСТВИЯ КЛИЕНТА (ОТМЕНА И ПОВТОР ПОИСКА) ---

@router.callback_query(F.data.startswith("client_cancel:"))
async def client_cancel_order_callback(callback: CallbackQuery):
    req_id = int(callback.data.split(":")[1])
    req = await get_request(req_id)

    if not req or req.get("telegram_id") != callback.from_user.id:
        await callback.answer("❌ Заказ не найден.", show_alert=True)
        return

    status = req.get("status")

    if status == "arrived":
        await callback.answer(
            "⚠️ Автомобиль уже ожидает вас на месте!\n"
            "Для отмены свяжитесь напрямую с водителем или диспетчером.",
            show_alert=True
        )
        return

    if status in ("done", "cancelled"):
        await callback.answer("Заказ уже завершён или отменён.", show_alert=True)
        return

    await cancel_request(req_id)

    drv_msg = driver_order_messages.get(req_id)
    if drv_msg:
        try:
            await callback.bot.edit_message_text(
                chat_id=drv_msg["chat_id"],
                message_id=drv_msg["message_id"],
                text=f"❌ <b>Заказ №{req_id} отменён клиентом.</b>",
                parse_mode="HTML"
            )
            driver_order_messages.pop(req_id, None)
        except Exception:
            pass

    driver_id = req.get("driver_id")
    if driver_id and status == "taken":
        try:
            await callback.bot.send_message(
                chat_id=driver_id,
                text=f"❌ <b>Клиент отменил поездку по заказу №{req_id}.</b>\nВы освобождены.",
                parse_mode="HTML"
            )
        except Exception:
            pass

    try:
        await callback.bot.send_message(
            chat_id=get_admin_id(),
            text=f"ℹ️ <b>Клиент самостоятельно отменил заказ №{req_id}</b> (статус был: {status}).",
            parse_mode="HTML"
        )
    except Exception:
        pass

    try:
        await callback.message.edit_text(
            f"❌ <b>Заказ №{req_id} успешно отменён вами.</b>\nЕсли потребуется такси, ждём вас снова!",
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(f"❌ <b>Заказ №{req_id} отменён.</b>", parse_mode="HTML")

    await callback.answer("Заказ отменён.")


@router.callback_query(F.data.startswith("client_retry:"))
async def client_retry_search_callback(callback: CallbackQuery):
    req_id = int(callback.data.split(":")[1])
    req = await get_request(req_id)

    if not req or req.get("status") != "new":
        await callback.answer("Заказ уже взят водителем или закрыт.", show_alert=True)
        return

    await callback.answer("🔄 Поиск продлён!")
    await callback.message.edit_text(
        f"🔄 <b>Поиск автомобиля по заказу №{req_id} продолжен.</b>\n"
        "Мы оповестим вас, как только водитель примет заказ.",
        parse_mode="HTML",
        reply_markup=client_cancel_keyboard(req_id)
    )

    asyncio.create_task(order_search_timeout_task(callback.bot, req_id, delay=SEARCH_TIMEOUT_SECONDS))


# --- ОБРАБОТКА НОВЫХ ЗАКАЗОВ ---

@router.message(F.contact)
async def handle_contact(message: Message):
    if not message.contact:
        return

    phone = message.contact.phone_number
    telegram_id = message.from_user.id
    updated_request = await save_phone(telegram_id, phone)

    await message.answer(f"✅ Ваш номер телефона <b>{phone}</b> успешно сохранён!", parse_mode="HTML")

    if updated_request and updated_request.get("admin_message_id"):
        try:
            admin_msg_text = (
                f"🚕 <b>ОБНОВЛЕНИЕ ЗАКАЗА №{updated_request['id']}</b>\n\n"
                f"{updated_request['ai_summary']}\n\n"
                f"📱 <b>Телефон клиента добавлен:</b> {phone}\n"
                f"📊 <b>Статус:</b> {updated_request['status']}"
            )
            await message.bot.send_message(get_admin_id(), admin_msg_text, parse_mode="HTML")
        except Exception:
            pass


@router.message(F.text | F.web_app_data)
async def handle_message(message: Message):
    if message.chat.id == get_drivers_chat_id():
        return

    user_id = message.from_user.id
    ban_info = await get_ban_info(user_id)
    if ban_info:
        reason = ban_info.get("reason", "Нарушение правил сервиса")
        await message.answer(
            f"⛔ <b>Ваш доступ к сервису такси ограничен.</b>\n\n<b>Причина:</b> {reason}\nЕсли произошла ошибка, свяжитесь с поддержкой.",
            parse_mode="HTML"
        )
        return

    raw_text = ""
    order_data = {}

    if message.web_app_data:
        try:
            order_data = json.loads(message.web_app_data.data)
            raw_text = order_data.get("text") or ""
        except Exception:
            raw_text = message.web_app_data.data
    else:
        raw_text = message.text or ""

    if raw_text.startswith("/") or raw_text in [
        "📋 Активные заказы", "📋 Последняя заявка", "📊 Статистика за сегодня",
        "🚗 Водители и авто", "📥 Выгрузить отчёт", "📚 История заказов",
        "⚙️ Управление тарифами", "ℹ️ Как это работает", "💼 Мой баланс"
    ]:
        return

    parsed = parse_order_text(raw_text)
    from_address = order_data.get("from") or parsed.get("from_address")
    to_address = order_data.get("to") or parsed.get("to_address")

    if not from_address or not to_address:
        await message.answer(
            "⚠️ <b>Не удалось определить маршрут поездки.</b>\n\n"
            "Напишите подробнее, например:\n"
            "<i>Терновского 160 — Пушкина 3, 1 человек, сейчас</i>\n"
            "или воспользуйтесь кнопкой <b>«🚖 Заказать через приложение»</b>.",
            parse_mode="HTML"
        )
        return

    distance_km = await get_route_distance(from_address, to_address)
    has_child_chair = order_data.get("has_child_chair") or parsed.get("has_child_chair", False)
    price_info = calculate_price(distance_km=distance_km, has_child_chair=has_child_chair) if distance_km else None

    if price_info:
        settings = await get_tariff_settings()
        if price_info["is_city"] and not settings["city_enabled"]:
            await message.answer("⚠️ Городские поездки временно приостановлены диспетчером.")
            return
        if not price_info["is_city"] and not settings["intercity_enabled"]:
            await message.answer("⚠️ Междугородние поездки временно приостановлены диспетчером.")
            return

    saved_phone = await get_user_phone(message.from_user.id)
    phone_display = saved_phone or "не указан"
    passengers = order_data.get("passengers") or parsed.get("passengers", 1)
    time_str = order_data.get("time") or parsed.get("time") or "сейчас"
    comment = order_data.get("comment") or ""

    summary = (
        f"📍 <b>Откуда:</b> {from_address}\n"
        f"🏁 <b>Куда:</b> {to_address}\n"
        f"👥 <b>Пассажиров:</b> {passengers}\n"
        f"🕐 <b>Время подачи:</b> {time_str}\n"
    )
    if has_child_chair:
        summary += "👶 <b>Детское кресло:</b> Да\n"
    if comment:
        summary += f"💬 <b>Пожелания:</b> {comment}\n"

    if distance_km and price_info:
        summary += f"📏 <b>Расстояние:</b> {distance_km} км\n💰 <b>Стоимость:</b> {price_info['price']} ₽"
    else:
        summary += "💰 <b>Стоимость:</b> рассчитывается диспетчером"

    request_id = await create_request(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        raw_text=raw_text,
        ai_summary=summary,
        distance_km=distance_km,
        price=price_info["price"] if price_info else None,
        phone=saved_phone
    )

    client_text = (
        f"🚕 <b>Заказ №{request_id} принят!</b>\n\n{summary}\n\n"
        "Ищем свободного водителя. Мы уведомим вас, когда машина будет назначена."
    )
    await message.answer(client_text, parse_mode="HTML", reply_markup=client_cancel_keyboard(request_id))

    asyncio.create_task(order_search_timeout_task(message.bot, request_id, delay=SEARCH_TIMEOUT_SECONDS))

    drivers_chat_id = get_drivers_chat_id()
    if drivers_chat_id:
        driver_card = f"🚕 <b>НОВЫЙ ЗАКАЗ №{request_id}</b>\n\n{summary}\n\nНажмите кнопку ниже, чтобы взять заказ:"
        try:
            drv_msg = await message.bot.send_message(
                chat_id=drivers_chat_id,
                text=driver_card,
                parse_mode="HTML",
                reply_markup=driver_want_keyboard(request_id)
            )
            driver_order_messages[request_id] = {
                "chat_id": drivers_chat_id,
                "message_id": drv_msg.message_id
            }
        except Exception as e:
            print("Ошибка отправки водителям:", e)

    try:
        from app.handlers.admin import order_keyboard
        req_dict = {
            "id": request_id,
            "telegram_id": message.from_user.id,
            "first_name": message.from_user.first_name,
            "username": message.from_user.username,
            "phone": saved_phone,
            "ai_summary": summary,
            "raw_text": raw_text,
            "status": "new"
        }
        adm_msg = await message.bot.send_message(
            chat_id=get_admin_id(),
            text=(
                f"🔔 <b>НОВАЯ ЗАЯВКА №{request_id}</b>\n\n"
                f"👤 Клиент: {message.from_user.first_name} (ID: <code>{message.from_user.id}</code>)\n"
                f"📱 Телефон: {phone_display}\n\n{summary}"
            ),
            parse_mode="HTML",
            reply_markup=order_keyboard(req_dict)
        )
        await save_admin_message_id(request_id, adm_msg.message_id)
    except Exception as e:
        print("Ошибка оповещения админа:", e)