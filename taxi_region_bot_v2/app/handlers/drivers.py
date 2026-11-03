from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import get_admin_id

from app.db import (
    get_request,
    add_driver_request,
    get_driver_requests,
    assign_driver,
    complete_request,
    cancel_request
)


router = Router()

print("drivers.py загружен")


# ============================================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ БЕЗОПАСНОГО ЧТЕНИЯ ROW
# ============================================================

def get_val(row, key, default=None):
    """Безопасно извлекает значение из sqlite3.Row или dict без AttributeError."""
    if row is None:
        return default
    try:
        val = row[key]
        return val if val is not None else default
    except (KeyError, IndexError):
        return default


# ============================================================
# ХРАНИМ ДАННЫЕ СООБЩЕНИЯ ЗАКАЗА В ГРУППЕ ВОДИТЕЛЕЙ
# ============================================================
driver_order_messages = {}


# ============================================================
# КЛАВИАТУРЫ
# ============================================================

def driver_accept_keyboard(request_id: int, driver_id: int):
    """Кнопка для администратора для утверждения водителя."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Принять водителя",
        callback_data=f"assign:{request_id}:{driver_id}"
    )
    return builder.as_markup()


def driver_action_keyboard(request_id: int):
    """Кнопки управления поездкой в личных сообщениях водителя."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🏁 Завершить заказ",
        callback_data=f"driver_finish:{request_id}"
    )
    builder.button(
        text="❌ Отменить поездку",
        callback_data=f"driver_cancel:{request_id}"
    )
    builder.adjust(1)
    return builder.as_markup()


# ============================================================
# ТЕСТОВЫЙ ВОДИТЕЛЬ
# ============================================================

@router.message(Command("test_driver"))
async def test_driver(message: Message):
    print()
    print("=" * 60)
    print("ПОЛУЧЕНА КОМАНДА /test_driver")
    print("USER ID:", message.from_user.id)
    print("TEXT:", message.text)
    print("=" * 60)

    if message.from_user.id != get_admin_id():
        print("⛔ Доступ запрещён.")
        return

    command_text = message.text or ""
    parts = command_text.split(maxsplit=1)

    if len(parts) < 2:
        await message.answer(
            "🧪 <b>ТЕСТ ВОДИТЕЛЯ</b>\n\n"
            "Укажите номер заказа.\n\n"
            "<b>Пример:</b>\n"
            "/test_driver 23",
            parse_mode="HTML"
        )
        return

    try:
        request_id = int(parts[1].strip())
    except ValueError:
        await message.answer("❌ Номер заказа должен быть числом.\nПример: /test_driver 23")
        return

    request = await get_request(request_id)
    if not request:
        await message.answer(f"❌ Заказ №{request_id} не найден.")
        return

    status = get_val(request, "status", "new")
    if status != "new":
        await message.answer(
            f"⚠️ Заказ №{request_id} уже имеет статус: {status}"
        )
        return

    driver_id = message.from_user.id
    driver_username = message.from_user.username
    driver_first_name = message.from_user.first_name or "Тестовый водитель"
    driver_name = f"@{driver_username}" if driver_username else driver_first_name

    success, result = await add_driver_request(
        request_id,
        driver_id,
        driver_username,
        driver_first_name
    )

    if not success:
        if result == "already_waiting":
            await message.answer(f"ℹ️ Тестовый водитель уже в списке заказа №{request_id}.")
            return
        if result == "taken":
            await message.answer(f"⚠️ Заказ №{request_id} уже назначен.")
            return
        await message.answer("❌ Не удалось добавить тестового водителя.")
        return

    ai_summary = get_val(request, "ai_summary")
    phone = get_val(request, "phone")

    admin_text = (
        f"🧪 <b>ТЕСТ: ВОДИТЕЛЬ ХОЧЕТ ЗАКАЗ №{request_id}</b>\n\n"
        f"👤 <b>Водитель:</b> {driver_name}\n"
        f"🆔 <b>ID:</b> {driver_id}\n\n"
    )
    if ai_summary:
        admin_text += f"📋 <b>Заказ:</b>\n{ai_summary}\n\n"
    if phone:
        admin_text += f"📱 <b>Телефон клиента:</b> {phone}\n\n"
    admin_text += "👇 <b>Назначить этого водителя?</b>"

    try:
        await message.bot.send_message(
            get_admin_id(),
            admin_text,
            parse_mode="HTML",
            reply_markup=driver_accept_keyboard(request_id, driver_id)
        )
    except Exception as error:
        print("❌ ОШИБКА ОТПРАВКИ ТЕСТОВОГО ВОДИТЕЛЯ АДМИНИСТРАТОРУ:", repr(error))
        await message.answer("❌ Не удалось отправить уведомление администратору.")
        return

    await message.answer(
        f"✅ <b>Тестовый отклик создан.</b>\n\n"
        f"🚕 Заказ №{request_id}\n"
        f"👤 Водитель: {driver_name}\n\n"
        "В сообщении администратора нажмите:\n"
        "✅ <b>Принять водителя</b>",
        parse_mode="HTML"
    )


# ============================================================
# ВОДИТЕЛЬ НАЖАЛ «БЕРУ ЗАКАЗ»
# ============================================================

@router.callback_query(F.data.startswith("driver_wants:"))
async def driver_wants_order(callback: CallbackQuery):
    print()
    print("=" * 60)
    print("ВОДИТЕЛЬ НАЖАЛ КНОПКУ БЕРУ ЗАКАЗ")
    print("USER ID:", callback.from_user.id)
    print("CHAT ID:", callback.message.chat.id)
    print("CALLBACK DATA:", callback.data)
    print("=" * 60)

    try:
        parts = callback.data.split(":")
        request_id = int(parts[1])
    except Exception as error:
        print("❌ ОШИБКА РАЗБОРА CALLBACK:", repr(error))
        await callback.answer("❌ Ошибка данных заказа.", show_alert=True)
        return

    driver_order_messages[request_id] = {
        "chat_id": callback.message.chat.id,
        "message_id": callback.message.message_id
    }

    request = await get_request(request_id)
    if not request:
        await callback.answer("❌ Заказ не найден.", show_alert=True)
        return

    status = get_val(request, "status", "new")
    if status != "new":
        await callback.answer("⚠️ Этот заказ уже назначен.", show_alert=True)
        return

    driver_id = callback.from_user.id
    driver_username = callback.from_user.username
    driver_first_name = callback.from_user.first_name
    driver_name = f"@{driver_username}" if driver_username else (driver_first_name or "водитель")

    success, result = await add_driver_request(
        request_id,
        driver_id,
        driver_username,
        driver_first_name
    )

    if not success:
        if result == "already_waiting":
            await callback.answer("ℹ️ Вы уже предложили себя на этот заказ.", show_alert=True)
            return
        if result == "taken":
            await callback.answer("⚠️ Заказ уже назначен.", show_alert=True)
            return
        await callback.answer("❌ Не удалось зарегистрировать заявку.", show_alert=True)
        return

    await callback.answer(
        "✅ Вы предложили себя на заказ.\nОжидайте решения администратора.",
        show_alert=True
    )

    ai_summary = get_val(request, "ai_summary")
    phone = get_val(request, "phone")

    admin_text = (
        f"🚕 <b>ВОДИТЕЛЬ ХОЧЕТ ЗАКАЗ №{request_id}</b>\n\n"
        f"👤 <b>Водитель:</b> {driver_name}\n"
        f"🆔 <b>ID:</b> {driver_id}\n\n"
    )
    if ai_summary:
        admin_text += f"📋 <b>Заказ:</b>\n{ai_summary}\n\n"
    if phone:
        admin_text += f"📱 <b>Телефон клиента:</b> {phone}\n\n"
    admin_text += "👇 <b>Назначить этого водителя?</b>"

    try:
        await callback.bot.send_message(
            get_admin_id(),
            admin_text,
            parse_mode="HTML",
            reply_markup=driver_accept_keyboard(request_id, driver_id)
        )
    except Exception as error:
        print("❌ ОШИБКА ОТПРАВКИ АДМИНИСТРАТОРУ:", repr(error))


# ============================================================
# АДМИНИСТРАТОР НАЖАЛ «ПРИНЯТЬ ВОДИТЕЛЯ»
# ============================================================

@router.callback_query(F.data.startswith("assign:"))
async def assign_driver_callback(callback: CallbackQuery):
    print()
    print("=" * 60)
    print("АДМИНИСТРАТОР НАЗНАЧАЕТ ВОДИТЕЛЯ")
    print("ADMIN ID:", callback.from_user.id)
    print("CALLBACK:", callback.data)
    print("=" * 60)

    if callback.from_user.id != get_admin_id():
        await callback.answer("⛔ Только администратор может назначить водителя.", show_alert=True)
        return

    try:
        parts = callback.data.split(":")
        request_id = int(parts[1])
        driver_id = int(parts[2])
    except Exception:
        await callback.answer("❌ Ошибка данных заказа.", show_alert=True)
        return

    request = await get_request(request_id)
    if not request:
        await callback.answer("❌ Заказ не найден.", show_alert=True)
        return

    status = get_val(request, "status", "new")
    if status != "new":
        await callback.answer("⚠️ Заказ уже назначен.", show_alert=True)
        return

    drivers = await get_driver_requests(request_id)
    selected_driver = None
    for d in drivers:
        if d["driver_id"] == driver_id:
            selected_driver = d
            break

    if not selected_driver:
        await callback.answer("❌ Водитель не найден среди желающих.", show_alert=True)
        return

    sel_driver_id = selected_driver["driver_id"]
    sel_driver_username = get_val(selected_driver, "driver_username")
    sel_driver_first_name = get_val(selected_driver, "driver_first_name")

    success = await assign_driver(
        request_id,
        sel_driver_id,
        sel_driver_username,
        sel_driver_first_name
    )

    if not success:
        await callback.answer("⚠️ Заказ уже был назначен.", show_alert=True)
        return

    driver_name = f"@{sel_driver_username}" if sel_driver_username else (sel_driver_first_name or "водитель")

    await callback.answer("✅ Водитель назначен.", show_alert=True)

    # 1. Обновляем сообщение администратора
    try:
        await callback.message.edit_text(
            f"✅ <b>ВОДИТЕЛЬ НАЗНАЧЕН</b>\n\n"
            f"🚕 <b>Заказ №{request_id}</b>\n"
            f"👤 <b>Водитель:</b> {driver_name}\n"
            f"🆔 <b>ID:</b> {sel_driver_id}",
            parse_mode="HTML"
        )
    except Exception as error:
        print("ОШИБКА ИЗМЕНЕНИЯ СООБЩЕНИЯ АДМИНА:", repr(error))

    # 2. Удаляем кнопку «Беру заказ» в группе водителей
    driver_group_message = driver_order_messages.get(request_id)
    group_chat_id = None
    if driver_group_message:
        group_chat_id = driver_group_message["chat_id"]
        group_message_id = driver_group_message["message_id"]
        try:
            await callback.bot.edit_message_reply_markup(
                chat_id=group_chat_id,
                message_id=group_message_id,
                reply_markup=None
            )
            driver_order_messages.pop(request_id, None)
        except Exception as error:
            print("❌ ОШИБКА УДАЛЕНИЯ КНОПКИ В ГРУППЕ ВОДИТЕЛЕЙ:", repr(error))

    # 3. Отправляем карточку водителю с кнопками действий
    ai_summary = get_val(request, "ai_summary", "")
    phone = get_val(request, "phone")

    driver_text = f"✅ <b>ВАМ НАЗНАЧЕН ЗАКАЗ №{request_id}</b>\n\n"
    if ai_summary:
        driver_text += f"{ai_summary}\n\n"
    if phone:
        driver_text += f"📱 <b>Телефон клиента:</b> {phone}\n\n"
    else:
        driver_text += "📱 <b>Телефон клиента:</b> Ожидается ввод...\n\n"
    driver_text += "Свяжитесь с клиентом. По окончании поездки нажмите кнопку ниже:"

    try:
        await callback.bot.send_message(
            sel_driver_id,
            driver_text,
            parse_mode="HTML",
            reply_markup=driver_action_keyboard(request_id)
        )
        print("✅ ДАННЫЕ ЗАКАЗА ОТПРАВЛЕНЫ ВОДИТЕЛЮ")
    except Exception as error:
        print("❌ ОШИБКА ОТПРАВКИ ВОДИТЕЛЮ:", repr(error))

    # 4. Оповещаем группу водителей
    try:
        target_chat = group_chat_id or callback.message.chat.id
        await callback.bot.send_message(
            target_chat,
            f"🔵 <b>ЗАКАЗ №{request_id} НАЗНАЧЕН</b>\n\n🚕 Водитель: {driver_name}",
            parse_mode="HTML"
        )
    except Exception as error:
        print("ОШИБКА ОТПРАВКИ В ГРУППУ ВОДИТЕЛЕЙ:", repr(error))

    # 5. ОПОВЕЩАЕМ КЛИЕНТА В ЛИЧНЫЕ СООБЩЕНИЯ
    client_telegram_id = get_val(request, "telegram_id")
    if client_telegram_id:
        try:
            client_text = (
                f"🚕 <b>Водитель назначен на ваш заказ №{request_id}!</b>\n\n"
                f"👤 <b>Водитель:</b> {driver_name}\n"
                "Водитель свяжется с вами в ближайшее время."
            )
            await callback.bot.send_message(
                chat_id=client_telegram_id,
                text=client_text,
                parse_mode="HTML"
            )
            print(f"✅ КЛИЕНТ (ID: {client_telegram_id}) ОПОВЕЩЁН О НАЗНАЧЕНИИ ВОДИТЕЛЯ")
        except Exception as client_err:
            print(f"❌ ОШИБКА ОПОВЕЩЕНИЯ КЛИЕНТА: {client_err}")


# ============================================================
# ВОДИТЕЛЬ ЗАВЕРШАЕТ ЗАКАЗ
# ============================================================

@router.callback_query(F.data.startswith("driver_finish:"))
async def driver_finish_order(callback: CallbackQuery):
    try:
        request_id = int(callback.data.split(":")[1])
    except Exception:
        await callback.answer("❌ Ошибка данных.", show_alert=True)
        return

    request = await get_request(request_id)
    if not request:
        await callback.answer("❌ Заказ не найден.", show_alert=True)
        return

    driver_id = get_val(request, "driver_id")
    if driver_id != callback.from_user.id:
        await callback.answer("⛔ Вы не являетесь водителем этого заказа.", show_alert=True)
        return

    status = get_val(request, "status", "new")
    if status == "done":
        await callback.answer("ℹ️ Заказ уже был завершён ранее.", show_alert=True)
        return

    await complete_request(request_id)

    await callback.message.edit_text(
        f"🏁 <b>Заказ №{request_id} успешно завершён!</b>\n\nСпасибо за работу.",
        parse_mode="HTML"
    )
    await callback.answer("✅ Заказ завершён.")

    client_id = get_val(request, "telegram_id")
    if client_id:
        try:
            await callback.bot.send_message(
                chat_id=client_id,
                text=f"🏁 <b>Поездка по заказу №{request_id} завершена.</b>\n\nСпасибо, что воспользовались нашей службой такси!",
                parse_mode="HTML"
            )
        except Exception as error:
            print("Ошибка отправки клиенту о завершении:", error)

    try:
        await callback.bot.send_message(
            chat_id=get_admin_id(),
            text=f"✅ <b>Заказ №{request_id} выполнен водителем.</b>\nСтатус переведён в 'done'.",
            parse_mode="HTML"
        )
    except Exception as error:
        print("Ошибка уведомления админа о завершении:", error)


# ============================================================
# ВОДИТЕЛЬ ОТМЕНЯЕТ ЗАКАЗ
# ============================================================

@router.callback_query(F.data.startswith("driver_cancel:"))
async def driver_cancel_order(callback: CallbackQuery):
    try:
        request_id = int(callback.data.split(":")[1])
    except Exception:
        await callback.answer("❌ Ошибка данных.", show_alert=True)
        return

    request = await get_request(request_id)
    if not request:
        await callback.answer("❌ Заказ не найден.", show_alert=True)
        return

    driver_id = get_val(request, "driver_id")
    if driver_id != callback.from_user.id:
        await callback.answer("⛔ Вы не являетесь водителем этого заказа.", show_alert=True)
        return

    await cancel_request(request_id)

    await callback.message.edit_text(
        f"❌ <b>Поездка по заказу №{request_id} отменена вами.</b>",
        parse_mode="HTML"
    )
    await callback.answer("Поездка отменена.")

    try:
        await callback.bot.send_message(
            chat_id=get_admin_id(),
            text=f"⚠️ <b>Внимание!</b> Водитель отменил поездку по заказу №{request_id}.",
            parse_mode="HTML"
        )
    except Exception as error:
        print("Ошибка оповещения админа об отмене:", error)