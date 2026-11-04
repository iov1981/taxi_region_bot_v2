import io
import csv
import html
import asyncio
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile
)
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from app.config import get_admin_id, get_drivers_chat_id
from app.keyboards import admin_menu, client_menu
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
    set_intercity_enabled,
    get_today_stats,
    set_driver_car,
    get_all_drivers,
    get_all_orders_for_export,
    ban_user,
    unban_user,
    clear_all_orders_db,
    get_all_client_ids,
    get_all_driver_ids
)

router = Router()
print("admin.py загружен")


def get_status_text(status: str) -> str:
    if status == "new":
        return "🟢 Новый"
    if status == "taken":
        return "🔵 В пути"
    if status == "arrived":
        return "🚖 Машина на месте"
    if status == "done":
        return "✅ Выполнен"
    if status == "cancelled":
        return "❌ Отменён"
    return status


def get_driver_text(request: dict) -> str:
    if not request.get("driver_id"):
        return "—"
    if request.get("driver_username"):
        return f"@{request['driver_username']}"
    return request.get("driver_first_name") or "водитель"


def order_keyboard(request: dict) -> InlineKeyboardMarkup:
    request_id = request["id"]
    client_id = request["telegram_id"]

    buttons = [
        [
            InlineKeyboardButton(text="📞 Телефон", callback_data=f"order_phone:{request_id}"),
            InlineKeyboardButton(text="🚕 Водители", callback_data=f"order_drivers:{request_id}")
        ]
    ]

    action_row = []
    if request["status"] == "new":
        action_row.append(InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel:{request_id}"))
    elif request["status"] in ("taken", "arrived"):
        action_row.append(InlineKeyboardButton(text="✅ Завершить", callback_data=f"complete:{request_id}"))
        action_row.append(InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel:{request_id}"))

    action_row.append(
        InlineKeyboardButton(text="⛔ Забанить", callback_data=f"ban_client:{client_id}:{request_id}")
    )
    buttons.append(action_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def tariff_keyboard() -> InlineKeyboardMarkup:
    settings = await get_tariff_settings()
    city_status = "🟢 ВКЛ" if settings["city_enabled"] else "🔴 ВЫКЛ"
    intercity_status = "🟢 ВКЛ" if settings["intercity_enabled"] else "🔴 ВЫКЛ"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🏙 Город: {city_status}", callback_data="tariff:city")],
            [InlineKeyboardButton(text=f"🛣 Межгород: {intercity_status}", callback_data="tariff:intercity")],
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="tariff:refresh")]
        ]
    )


# --- СТАРТ ---

@router.message(CommandStart())
async def start_cmd(message: Message):
    user_id = message.from_user.id
    if user_id == get_admin_id():
        await message.answer(
            "👋 <b>Добро пожаловать в панель администратора!</b>\n\n"
            "Выберите необходимое действие в меню ниже:",
            reply_markup=admin_menu(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "👋 <b>Добро пожаловать в сервис заказа такси!</b>\n\n"
            "Вы можете быстро оформить поездку через приложение "
            "или просто написать маршрут в чат (например: <i>Терновского 152 — Калинина 68</i>).",
            reply_markup=client_menu(),
            parse_mode="HTML"
        )


# --- ПОЛНОЕ УДАЛЕНИЕ ЗАКАЗОВ ---

@router.message(Command("clear_orders"))
async def clear_all_orders_cmd(message: Message):
    if message.from_user.id != get_admin_id():
        return

    await clear_all_orders_db()
    await message.answer(
        "🧹 <b>Все заказы, отклики и отзывы успешно удалены!</b>\n\n"
        "Счётчик заявок сброшен на №1, статистика и баланс обнулены.",
        parse_mode="HTML"
    )


# --- БАН / РАЗБАН ---

@router.message(Command("ban"))
async def admin_ban_cmd(message: Message):
    if message.from_user.id != get_admin_id():
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        await message.answer(
            "⛔ <b>Блокировка пользователя</b>\n\nФормат: <code>/ban ID_пользователя Причина</code>",
            parse_mode="HTML"
        )
        return

    try:
        target_id = int(parts[1].strip())
    except ValueError:
        await message.answer("❌ ID пользователя должен быть числом.")
        return

    reason = parts[2].strip() if len(parts) > 2 else "Нарушение правил сервиса"
    await ban_user(target_id, reason)

    await message.answer(
        f"⛔ <b>Пользователь заблокирован!</b>\n🆔 ID: <code>{target_id}</code>\n📝 Причина: {html.escape(reason)}",
        parse_mode="HTML"
    )


@router.message(Command("unban"))
async def admin_unban_cmd(message: Message):
    if message.from_user.id != get_admin_id():
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("✅ <b>Разблокировка</b>\n\nФормат: <code>/unban ID_пользователя</code>", parse_mode="HTML")
        return

    try:
        target_id = int(parts[1].strip())
    except ValueError:
        await message.answer("❌ ID пользователя должен быть числом.")
        return

    success = await unban_user(target_id)
    if success:
        await message.answer(f"✅ Пользователь <code>{target_id}</code> успешно разблокирован.", parse_mode="HTML")
    else:
        await message.answer(f"ℹ️ Пользователь <code>{target_id}</code> не был найден в чёрном списке.", parse_mode="HTML")


@router.callback_query(F.data.startswith("ban_client:"))
async def ban_client_callback(callback: CallbackQuery):
    if callback.from_user.id != get_admin_id():
        await callback.answer("❌ Только администратор.", show_alert=True)
        return

    parts = callback.data.split(":")
    client_id = int(parts[1])
    request_id = int(parts[2])

    await ban_user(client_id, f"Блокировка по заказу №{request_id}")
    await callback.answer(f"⛔ Клиент {client_id} заблокирован!", show_alert=True)

    await callback.bot.send_message(
        chat_id=get_admin_id(),
        text=f"⛔ <b>Клиент {client_id} добавлен в чёрный список</b> по заказу №{request_id}.\nДля разблокировки используйте: <code>/unban {client_id}</code>",
        parse_mode="HTML"
    )


# --- РАССЫЛКА ВОДИТЕЛЯМ ---

@router.message(Command("broadcast_drivers"))
async def broadcast_drivers_cmd(message: Message):
    if message.from_user.id != get_admin_id():
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "📢 <b>Рассылка водителям</b>\n\n"
            "Формат: <code>/broadcast_drivers Текст вашего сообщения</code>\n\n"
            "<i>Пример: /broadcast_drivers Внимание! На дорогах гололёд, соблюдайте дистанцию.</i>",
            parse_mode="HTML"
        )
        return

    broadcast_text = parts[1].strip()
    driver_ids = await get_all_driver_ids()

    formatted_msg = (
        "📢 <b>СООБЩЕНИЕ ОТ ДИСПЕТЧЕРА ДЛЯ ВОДИТЕЛЕЙ</b>\n"
        "──────────────────────\n\n"
        f"{html.escape(broadcast_text)}"
    )

    success_count = 0
    blocked_count = 0

    status_msg = await message.answer("⏳ Выполняется рассылка водителям...")

    for d_id in driver_ids:
        try:
            await message.bot.send_message(chat_id=d_id, text=formatted_msg, parse_mode="HTML")
            success_count += 1
            await asyncio.sleep(0.05)
        except TelegramForbiddenError:
            blocked_count += 1
        except Exception:
            pass

    drivers_group_id = get_drivers_chat_id()
    if drivers_group_id:
        try:
            await message.bot.send_message(chat_id=drivers_group_id, text=formatted_msg, parse_mode="HTML")
        except Exception as e:
            print("Ошибка отправки рассылки в группу водителей:", e)

    await status_msg.edit_text(
        "✅ <b>Рассылка водителям завершена!</b>\n\n"
        f"👥 Зарегистрировано водителей: <b>{len(driver_ids)}</b>\n"
        f"📨 Доставлено успешно: <b>{success_count}</b>\n"
        f"🚫 Заблокировали бота: <b>{blocked_count}</b>\n"
        "📢 Сообщение также отправлено в чат водителей.",
        parse_mode="HTML"
    )


# --- РАССЫЛКА КЛИЕНТАМ ---

@router.message(Command("broadcast_clients"))
async def broadcast_clients_cmd(message: Message):
    if message.from_user.id != get_admin_id():
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "📢 <b>Рассылка клиентам</b>\n\n"
            "Формат: <code>/broadcast_clients Текст акции или сообщения</code>\n\n"
            "<i>Пример: /broadcast_clients Рады сообщить о запуске новых междугородних маршрутов!</i>",
            parse_mode="HTML"
        )
        return

    broadcast_text = parts[1].strip()
    client_ids = await get_all_client_ids()

    if not client_ids:
        await message.answer("ℹ️ В базе пока нет зарегистрированных клиентов.")
        return

    formatted_msg = (
        "🚕 <b>СЛУЖБА ЗАКАЗА ТАКСИ</b>\n"
        "──────────────────────\n\n"
        f"{html.escape(broadcast_text)}"
    )

    success_count = 0
    blocked_count = 0

    status_msg = await message.answer(f"⏳ Отправка сообщения клиентам (всего {len(client_ids)})...")

    for c_id in client_ids:
        try:
            await message.bot.send_message(chat_id=c_id, text=formatted_msg, parse_mode="HTML")
            success_count += 1
            await asyncio.sleep(0.05)
        except TelegramForbiddenError:
            blocked_count += 1
        except Exception:
            pass

    await status_msg.edit_text(
        "✅ <b>Рассылка клиентам завершена!</b>\n\n"
        f"👥 Всего клиентов в базе: <b>{len(client_ids)}</b>\n"
        f"📨 Доставлено успешно: <b>{success_count}</b>\n"
        f"🚫 Заблокировали бота: <b>{blocked_count}</b>",
        parse_mode="HTML"
    )


# --- ВЫГРУЗКА CSV ---

@router.message(F.text == "📥 Выгрузить отчёт")
async def export_orders_report(message: Message):
    if message.from_user.id != get_admin_id():
        return

    orders = await get_all_orders_for_export()
    if not orders:
        await message.answer("ℹ️ В базе пока нет заказов для выгрузки.")
        return

    wait_msg = await message.answer("⏳ Формирую отчёт...")

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

    writer.writerow([
        "№ Заказа", "Дата создания", "ID Клиента", "Имя клиента", "Телефон",
        "Маршрут / Сообщение", "Дистанция (км)", "Сумма заказа (₽)",
        "Комиссия сервиса (₽)", "Выплата водителю (₽)", "Статус",
        "Водитель", "Автомобиль", "Оценка клиента (1-5)"
    ])

    for o in orders:
        status_map = {
            "new": "Новый", "taken": "В пути", "arrived": "На месте",
            "done": "Выполнен", "cancelled": "Отменён"
        }
        status_ru = status_map.get(o.get("status"), o.get("status"))

        driver_display = o.get("driver_first_name") or ""
        if o.get("driver_username"):
            driver_display += f" (@{o['driver_username']})"

        writer.writerow([
            o.get("id"), o.get("created_at"), o.get("telegram_id"),
            o.get("first_name") or "", o.get("phone") or "Не указан",
            (o.get("raw_text") or "").replace("\n", " "),
            o.get("distance_km") or "", o.get("price") or "",
            o.get("commission") or 0, o.get("driver_payout") or 0,
            status_ru, driver_display.strip(), o.get("car_info") or "", o.get("rating") or ""
        ])

    csv_data = output.getvalue().encode("utf-8-sig")
    output.close()

    now_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    document = BufferedInputFile(file=csv_data, filename=f"orders_report_{now_str}.csv")

    try:
        await message.answer_document(
            document=document,
            caption=f"📊 <b>Отчёт успешно сформирован!</b> Всего заказов: <b>{len(orders)}</b>",
            parse_mode="HTML"
        )
    finally:
        await wait_msg.delete()


# --- АВТОМОБИЛИ ---

@router.message(Command("set_car"))
async def admin_set_car(message: Message):
    if message.from_user.id != get_admin_id():
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "🚗 <b>Привязка автомобиля</b>\nФормат: <code>/set_car ID_водителя Марка, Цвет, Госномер</code>",
            parse_mode="HTML"
        )
        return

    try:
        target_driver_id = int(parts[1].strip())
    except ValueError:
        await message.answer("❌ ID водителя должен быть числом.")
        return

    car_data = parts[2].strip()
    await set_driver_car(driver_id=target_driver_id, car_info=car_data, driver_name="Водитель")

    await message.answer(
        f"✅ <b>Автомобиль привязан!</b>\n🆔 ID: <code>{target_driver_id}</code>\n🚗 Авто: {html.escape(car_data)}",
        parse_mode="HTML"
    )


@router.message(F.text == "🚗 Водители и авто")
async def show_drivers_cars(message: Message):
    if message.from_user.id != get_admin_id():
        return

    drivers = await get_all_drivers()
    if not drivers:
        await message.answer("🚗 База автомобилей пуста.\nПривязка: <code>/set_car ID Данные</code>", parse_mode="HTML")
        return

    text = "🚗 <b>ЗАРЕГИСТРИРОВАННЫЙ АВТОПАРК:</b>\n\n"
    for d in drivers:
        d_name = f"@{d['driver_username']}" if d.get("driver_username") else (d.get("driver_name") or "водитель")
        car = d.get("car_info") or "не указан"
        rating = f"{d.get('rating', 5.0)} ⭐️"
        text += (
            f"👤 <b>{html.escape(d_name)}</b> (ID: <code>{d['driver_id']}</code>)\n"
            f"   🚗 {html.escape(car)}\n"
            f"   ⭐️ Рейтинг: {rating} (отзывов: {d.get('rating_count', 0)})\n\n"
        )
    await message.answer(text, parse_mode="HTML")


# --- СТАТИСТИКА ЗА СЕГОДНЯ ---

@router.message(F.text == "📊 Статистика за сегодня")
async def show_today_stats(message: Message):
    if message.from_user.id != get_admin_id():
        return

    stats = await get_today_stats()
    text = (
        "📊 <b>ФИНАНСОВЫЙ ОТЧЁТ ЗА СЕГОДНЯ:</b>\n\n"
        f"📝 <b>Поступило заказов:</b> {stats['created_orders']}\n"
        f"✅ <b>Выполнено поездок:</b> {stats['done_orders']}\n"
        f"📏 <b>Суммарный пробег:</b> {stats['total_distance']} км\n"
        "──────────────────────\n"
        f"💰 <b>Общая касса:</b> {stats['total_revenue']:,} ₽\n"
        f"💼 <b>Прибыль сервиса (комиссия):</b> {stats['total_commission']:,} ₽\n"
        f"🚕 <b>Выплачено водителям:</b> {stats['total_driver_payout']:,} ₽"
    ).replace(",", " ")

    await message.answer(text, parse_mode="HTML")


# --- ТАРИФЫ ---

@router.message(F.text == "⚙️ Управление тарифами")
async def tariff_settings(message: Message):
    if message.from_user.id != get_admin_id():
        return

    settings = await get_tariff_settings()
    city_status = "🟢 ВКЛ" if settings["city_enabled"] else "🔴 ВЫКЛ"
    intercity_status = "🟢 ВКЛ" if settings["intercity_enabled"] else "🔴 ВЫКЛ"

    await message.answer(
        f"⚙️ <b>УПРАВЛЕНИЕ ТАРИФАМИ</b>\n\n🏙 Город: {city_status}\n🛣 Межгород: {intercity_status}",
        reply_markup=await tariff_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "tariff:city")
async def toggle_city_tariff(callback: CallbackQuery):
    if callback.from_user.id != get_admin_id():
        return

    settings = await get_tariff_settings()
    new_value = not settings["city_enabled"]
    await set_city_enabled(new_value)

    await callback.message.edit_reply_markup(reply_markup=await tariff_keyboard())
    await callback.answer(f"🏙 Городской тариф {'включён' if new_value else 'выключен'}")


@router.callback_query(F.data == "tariff:intercity")
async def toggle_intercity_tariff(callback: CallbackQuery):
    if callback.from_user.id != get_admin_id():
        return

    settings = await get_tariff_settings()
    new_value = not settings["intercity_enabled"]
    await set_intercity_enabled(new_value)

    await callback.message.edit_reply_markup(reply_markup=await tariff_keyboard())
    await callback.answer(f"🛣 Межгородской тариф {'включён' if new_value else 'выключен'}")


@router.callback_query(F.data == "tariff:refresh")
async def refresh_tariffs(callback: CallbackQuery):
    try:
        await callback.message.edit_reply_markup(reply_markup=await tariff_keyboard())
    except TelegramBadRequest:
        pass
    await callback.answer("🔄 Обновлено")


# --- ЗАКАЗЫ ---

@router.callback_query(F.data.startswith("order_phone:"))
async def order_phone(callback: CallbackQuery):
    req_id = int(callback.data.split(":")[1])
    req = await get_request(req_id)
    phone = req.get("phone") or "не указан" if req else "не найден"
    await callback.answer(f"📞 Телефон: {phone}", show_alert=True)


@router.callback_query(F.data.startswith("order_drivers:"))
async def order_drivers(callback: CallbackQuery):
    req_id = int(callback.data.split(":")[1])
    request = await get_request(req_id)
    if not request:
        await callback.answer("❌ Заказ не найден.", show_alert=True)
        return

    drivers = await get_driver_requests(req_id)
    if not drivers:
        await callback.answer("🚕 Пока никто из водителей не откликнулся.", show_alert=True)
        return

    buttons = []
    for d in drivers:
        d_name = f"@{d['driver_username']}" if d.get("driver_username") else (d.get("driver_first_name") or "водитель")
        buttons.append([InlineKeyboardButton(text=f"✅ {d_name}", callback_data=f"assign:{req_id}:{d['driver_id']}")])

    await callback.message.answer(
        f"🚕 <b>ВОДИТЕЛИ НА ЗАКАЗ №{req_id}</b>\nВыберите для назначения:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(F.text == "📋 Последняя заявка")
async def last_request(message: Message):
    if message.from_user.id != get_admin_id():
        return

    request = await get_last_request()
    if not request:
        await message.answer("📋 Заявок пока нет.")
        return

    client_display = html.escape(str(request.get("first_name") or "клиент"))
    text = (
        f"🚕 <b>ЗАЯВКА №{request['id']}</b>\n\n"
        f"👤 Клиент: {client_display} (ID: <code>{request['telegram_id']}</code>)\n\n"
        f"{request['ai_summary']}\n\n"
        f"📞 Телефон: {request.get('phone') or 'не указан'}\n"
        f"📊 Статус: {get_status_text(request['status'])}\n"
        f"🚕 Водитель: {get_driver_text(request)}"
    )
    await message.answer(text, reply_markup=order_keyboard(request), parse_mode="HTML")


@router.message(F.text == "📋 Активные заказы")
async def active_requests(message: Message):
    if message.from_user.id != get_admin_id() or message.chat.type != "private":
        return

    requests = await get_active_requests()
    if not requests:
        await message.answer("📋 Активных заказов нет.")
        return

    await message.answer(f"📋 <b>АКТИВНЫЕ ЗАКАЗЫ: {len(requests)}</b>", parse_mode="HTML")
    for req in requests:
        text = (
            f"🚕 <b>ЗАКАЗ №{req['id']}</b>\n\n"
            f"{req['ai_summary']}\n\n"
            f"📞 Телефон: {req.get('phone') or 'не указан'}\n"
            f"📊 Статус: {get_status_text(req['status'])}\n"
            f"🚕 Водитель: {get_driver_text(req)}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f"🚕 Открыть заказ №{req['id']}", callback_data=f"active_order:{req['id']}")
        ]])
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("active_order:"))
async def active_order(callback: CallbackQuery):
    req_id = int(callback.data.split(":")[1])
    req = await get_request(req_id)
    if not req:
        await callback.answer("❌ Заказ не найден.", show_alert=True)
        return

    text = (
        f"🚕 <b>ЗАКАЗ №{req['id']}</b>\n\n"
        f"{req['ai_summary']}\n\n"
        f"📞 Телефон: {req.get('phone') or 'не указан'}\n"
        f"📊 Статус: {get_status_text(req['status'])}\n"
        f"🚕 Водитель: {get_driver_text(req)}"
    )
    await callback.message.answer(text, reply_markup=order_keyboard(req), parse_mode="HTML")
    await callback.answer()


@router.message(F.text == "📚 История заказов")
async def order_history(message: Message):
    if message.from_user.id != get_admin_id():
        return

    requests = await get_order_history(limit=15)
    if not requests:
        await message.answer("📚 История заказов пуста.")
        return

    await message.answer(f"📚 <b>ИСТОРИЯ ЗАКАЗОВ ({len(requests)}):</b>", parse_mode="HTML")
    for r in requests:
        await message.answer(
            f"🚕 <b>ЗАКАЗ №{r['id']}</b> | {get_status_text(r['status'])}\n"
            f"{r['ai_summary']}\n🚕 Водитель: {get_driver_text(r)}\n🕐 {r.get('created_at', '')}",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("complete:"))
async def complete_order(callback: CallbackQuery):
    if callback.from_user.id != get_admin_id():
        return

    req_id = int(callback.data.split(":")[1])
    request = await get_request(req_id)
    if not request or request["status"] not in ("taken", "arrived"):
        await callback.answer("⚠️ Заказ не в работе.", show_alert=True)
        return

    calc = await complete_request(req_id)

    await callback.message.edit_text(
        f"🚕 <b>ЗАКАЗ №{req_id}</b>\n\n"
        f"{request['ai_summary']}\n\n"
        f"🚕 Водитель: {get_driver_text(request)}\n\n"
        f"✅ <b>ЗАКАЗ УСПЕШНО ВЫПОЛНЕН</b>\n"
        f"💰 Сумма: <b>{calc['price']} ₽</b>\n"
        f"💼 Комиссия сервиса ({calc['percent']}%): <b>{calc['commission']} ₽</b>\n"
        f"💵 К выплате водителю: <b>{calc['driver_payout']} ₽</b>",
        parse_mode="HTML"
    )
    await callback.answer("✅ Заказ завершён")

    if request.get("telegram_id"):
        try:
            from app.handlers.drivers import client_rating_keyboard
            await callback.bot.send_message(
                chat_id=request["telegram_id"],
                text=f"🏁 <b>Поездка по заказу №{req_id} завершена!</b>\nПожалуйста, оцените поездку:",
                parse_mode="HTML",
                reply_markup=client_rating_keyboard(req_id)
            )
        except Exception:
            pass

    if request.get("driver_id"):
        try:
            await callback.bot.send_message(
                chat_id=request["driver_id"],
                text=(
                    f"🏁 <b>Заказ №{req_id} закрыт администратором.</b>\n\n"
                    f"💰 Сумма: <b>{calc['price']} ₽</b>\n"
                    f"💼 Комиссия ({calc['percent']}%): <b>{calc['commission']} ₽</b>\n"
                    f"💵 Чистый доход: <b>{calc['driver_payout']} ₽</b>"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("cancel:"))
async def cancel_order(callback: CallbackQuery):
    if callback.from_user.id != get_admin_id():
        return

    req_id = int(callback.data.split(":")[1])
    request = await get_request(req_id)
    if not request or request["status"] in ("done", "cancelled"):
        await callback.answer("⚠️ Заказ уже закрыт.", show_alert=True)
        return

    await cancel_request(req_id)
    await callback.message.edit_text(
        f"🚕 <b>ЗАКАЗ №{req_id}</b>\n\n{request['ai_summary']}\n\n❌ <b>ЗАКАЗ ОТМЕНЁН</b>",
        parse_mode="HTML"
    )
    await callback.answer("❌ Заказ отменён")

    for uid in [request.get("telegram_id"), request.get("driver_id")]:
        if uid:
            try:
                await callback.bot.send_message(
                    chat_id=uid,
                    text=f"❌ <b>Заказ №{req_id} был отменён диспетчером.</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass