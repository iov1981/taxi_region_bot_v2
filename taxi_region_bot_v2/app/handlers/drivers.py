from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import get_admin_id

from app.db import (
    get_request,
    add_driver_request,
    get_driver_requests,
    assign_driver
)


router = Router()

print("drivers.py загружен")


# ============================================================
# ХРАНИМ ДАННЫЕ СООБЩЕНИЯ ЗАКАЗА В ГРУППЕ ВОДИТЕЛЕЙ
# ============================================================
#
# request_id -> {
#     "chat_id": ID группы,
#     "message_id": ID сообщения
# }
#
# Например:
#
# 17 -> {
#     "chat_id": -5597678940,
#     "message_id": 307
# }
#
# Это нужно для того, чтобы после назначения водителя
# удалить кнопку «🟢 БЕРУ ЗАКАЗ» именно из сообщения
# в группе водителей.
#

driver_order_messages = {}


# ============================================================
# КНОПКА ДЛЯ АДМИНИСТРАТОРА
# ============================================================

def driver_accept_keyboard(
        request_id,
        driver_id
):

    builder = InlineKeyboardBuilder()

    builder.button(
        text="✅ Принять водителя",
        callback_data=f"assign:{request_id}:{driver_id}"
    )

    return builder.as_markup()


# ============================================================
# ВОДИТЕЛЬ НАЖАЛ «БЕРУ ЗАКАЗ»
# ============================================================

@router.callback_query(
    F.data.startswith("driver_wants:")
)
async def driver_wants_order(
        callback: CallbackQuery
):

    print()
    print("=" * 60)
    print("ВОДИТЕЛЬ НАЖАЛ КНОПКУ БЕРУ ЗАКАЗ")
    print("=" * 60)

    print(
        "USER ID:",
        callback.from_user.id
    )

    print(
        "USERNAME:",
        callback.from_user.username
    )

    print(
        "NAME:",
        callback.from_user.first_name
    )

    print(
        "CHAT ID:",
        callback.message.chat.id
    )

    print(
        "MESSAGE ID:",
        callback.message.message_id
    )

    print(
        "CALLBACK DATA:",
        callback.data
    )

    print("=" * 60)

    # ========================================================
    # НОМЕР ЗАКАЗА
    # ========================================================

    try:

        parts = callback.data.split(":")

        request_id = int(
            parts[1]
        )

    except Exception as error:

        print(
            "❌ ОШИБКА РАЗБОРА CALLBACK:",
            repr(error)
        )

        await callback.answer(
            "❌ Ошибка данных заказа.",
            show_alert=True
        )

        return

    print(
        "REQUEST ID:",
        request_id
    )

    # ========================================================
    # СОХРАНЯЕМ CHAT ID И MESSAGE ID ГРУППЫ
    # ========================================================

    driver_order_messages[request_id] = {
        "chat_id": callback.message.chat.id,
        "message_id": callback.message.message_id
    }

    print(
        "✅ ДАННЫЕ СООБЩЕНИЯ В ГРУППЕ СОХРАНЕНЫ"
    )

    print(
        "GROUP CHAT ID:",
        callback.message.chat.id
    )

    print(
        "MESSAGE ID:",
        callback.message.message_id
    )

    # ========================================================
    # ПОЛУЧАЕМ ЗАКАЗ
    # ========================================================

    request = await get_request(
        request_id
    )

    if not request:

        print(
            "❌ ЗАКАЗ НЕ НАЙДЕН:",
            request_id
        )

        await callback.answer(
            "❌ Заказ не найден.",
            show_alert=True
        )

        return

    print(
        "✅ ЗАКАЗ НАЙДЕН"
    )

    print(
        "STATUS:",
        request["status"]
    )

    # ========================================================
    # ПРОВЕРЯЕМ СТАТУС
    # ========================================================

    if request["status"] != "new":

        await callback.answer(
            "⚠️ Этот заказ уже назначен.",
            show_alert=True
        )

        return

    # ========================================================
    # ДАННЫЕ ВОДИТЕЛЯ
    # ========================================================

    driver_id = callback.from_user.id

    driver_username = (
        callback.from_user.username
    )

    driver_first_name = (
        callback.from_user.first_name
    )

    if driver_username:

        driver_name = (
            f"@{driver_username}"
        )

    else:

        driver_name = (
            driver_first_name
            or "водитель"
        )

    print()
    print("=" * 60)
    print("ВОДИТЕЛЬ")
    print("=" * 60)

    print(
        "DRIVER ID:",
        driver_id
    )

    print(
        "USERNAME:",
        driver_username
    )

    print(
        "NAME:",
        driver_first_name
    )

    print(
        "DISPLAY NAME:",
        driver_name
    )

    print("=" * 60)

    # ========================================================
    # ДОБАВЛЯЕМ ВОДИТЕЛЯ В СПИСОК ЖЕЛАЮЩИХ
    # ========================================================

    success, result = await add_driver_request(
        request_id,
        driver_id,
        driver_username,
        driver_first_name
    )

    print()
    print("=" * 60)
    print("РЕЗУЛЬТАТ ДОБАВЛЕНИЯ ВОДИТЕЛЯ")
    print("=" * 60)

    print(
        "SUCCESS:",
        success
    )

    print(
        "RESULT:",
        result
    )

    print("=" * 60)

    if not success:

        if result == "already_waiting":

            await callback.answer(
                "ℹ️ Вы уже предложили себя "
                "на этот заказ.",
                show_alert=True
            )

            return

        if result == "taken":

            await callback.answer(
                "⚠️ Заказ уже назначен.",
                show_alert=True
            )

            return

        await callback.answer(
            "❌ Не удалось зарегистрировать "
            "заявку.",
            show_alert=True
        )

        return

    # ========================================================
    # ПОДТВЕРЖДЕНИЕ ВОДИТЕЛЮ
    # ========================================================

    await callback.answer(
        "✅ Вы предложили себя на заказ.\n"
        "Ожидайте решения администратора.",
        show_alert=True
    )

    # ========================================================
    # СООБЩЕНИЕ АДМИНИСТРАТОРУ
    # ========================================================

    admin_text = (
        f"🚕 <b>ВОДИТЕЛЬ ХОЧЕТ ЗАКАЗ №{request_id}</b>\n\n"
        f"👤 <b>Водитель:</b> {driver_name}\n"
        f"🆔 <b>ID:</b> {driver_id}\n\n"
    )

    if request["ai_summary"]:

        admin_text += (
            "📋 <b>Заказ:</b>\n"
            f"{request['ai_summary']}\n\n"
        )

    if request["phone"]:

        admin_text += (
            "📱 <b>Телефон клиента:</b> "
            f"{request['phone']}\n\n"
        )

    admin_text += (
        "👇 <b>Назначить этого водителя?</b>"
    )

    # ========================================================
    # ОТПРАВКА АДМИНУ
    # ========================================================

    try:

        await callback.bot.send_message(
            get_admin_id(),
            admin_text,
            parse_mode="HTML",
            reply_markup=driver_accept_keyboard(
                request_id,
                driver_id
            )
        )

        print()
        print("=" * 60)
        print("✅ ВОДИТЕЛЬ ОТПРАВЛЕН АДМИНИСТРАТОРУ")
        print("=" * 60)

        print(
            "REQUEST ID:",
            request_id
        )

        print(
            "DRIVER ID:",
            driver_id
        )

        print("=" * 60)

    except Exception as error:

        print()
        print(
            "❌ ОШИБКА ОТПРАВКИ АДМИНИСТРАТОРУ"
        )

        print(
            type(error).__name__,
            repr(error)
        )


# ============================================================
# АДМИНИСТРАТОР НАЖАЛ «ПРИНЯТЬ ВОДИТЕЛЯ»
# ============================================================

@router.callback_query(
    F.data.startswith("assign:")
)
async def assign_driver_callback(
        callback: CallbackQuery
):

    print()
    print("=" * 60)
    print("АДМИНИСТРАТОР НАЗНАЧАЕТ ВОДИТЕЛЯ")
    print("=" * 60)

    print(
        "ADMIN ID:",
        callback.from_user.id
    )

    print(
        "CALLBACK:",
        callback.data
    )

    print("=" * 60)

    # ========================================================
    # ПРОВЕРКА АДМИНИСТРАТОРА
    # ========================================================

    if callback.from_user.id != get_admin_id():

        await callback.answer(
            "⛔ Только администратор "
            "может назначить водителя.",
            show_alert=True
        )

        return

    # ========================================================
    # РАЗБОР CALLBACK
    # ========================================================

    try:

        parts = callback.data.split(":")

        request_id = int(
            parts[1]
        )

        driver_id = int(
            parts[2]
        )

    except Exception:

        await callback.answer(
            "❌ Ошибка данных заказа.",
            show_alert=True
        )

        return

    # ========================================================
    # ПОЛУЧАЕМ ЗАКАЗ
    # ========================================================

    request = await get_request(
        request_id
    )

    if not request:

        await callback.answer(
            "❌ Заказ не найден.",
            show_alert=True
        )

        return

    if request["status"] != "new":

        await callback.answer(
            "⚠️ Заказ уже назначен.",
            show_alert=True
        )

        return

    # ========================================================
    # ИЩЕМ ВОДИТЕЛЯ
    # ========================================================

    drivers = await get_driver_requests(
        request_id
    )

    selected_driver = None

    for driver in drivers:

        if driver["driver_id"] == driver_id:

            selected_driver = driver

            break

    if not selected_driver:

        await callback.answer(
            "❌ Водитель не найден "
            "среди желающих.",
            show_alert=True
        )

        return

    # ========================================================
    # НАЗНАЧАЕМ ВОДИТЕЛЯ
    # ========================================================

    success = await assign_driver(
        request_id,
        selected_driver["driver_id"],
        selected_driver["driver_username"],
        selected_driver["driver_first_name"]
    )

    if not success:

        await callback.answer(
            "⚠️ Заказ уже был назначен.",
            show_alert=True
        )

        return

    # ========================================================
    # ИМЯ ВОДИТЕЛЯ
    # ========================================================

    if selected_driver["driver_username"]:

        driver_name = (
            f"@{selected_driver['driver_username']}"
        )

    else:

        driver_name = (
            selected_driver["driver_first_name"]
            or "водитель"
        )

    print()
    print("=" * 60)
    print("✅ ВОДИТЕЛЬ НАЗНАЧЕН")
    print("=" * 60)

    print(
        "REQUEST ID:",
        request_id
    )

    print(
        "DRIVER:",
        driver_name
    )

    print(
        "DRIVER ID:",
        selected_driver["driver_id"]
    )

    print("=" * 60)

    await callback.answer(
        "✅ Водитель назначен.",
        show_alert=True
    )

    # ========================================================
    # ОБНОВЛЯЕМ СООБЩЕНИЕ АДМИНА
    # ========================================================

    try:

        await callback.message.edit_text(
            f"✅ <b>ВОДИТЕЛЬ НАЗНАЧЕН</b>\n\n"
            f"🚕 <b>Заказ №{request_id}</b>\n"
            f"👤 <b>Водитель:</b> {driver_name}\n"
            f"🆔 <b>ID:</b> "
            f"{selected_driver['driver_id']}",
            parse_mode="HTML"
        )

    except Exception as error:

        print(
            "ОШИБКА ИЗМЕНЕНИЯ СООБЩЕНИЯ АДМИНА:",
            repr(error)
        )

    # ========================================================
    # УДАЛЯЕМ КНОПКУ «БЕРУ ЗАКАЗ» В ГРУППЕ
    # ========================================================

    driver_group_message = (
        driver_order_messages.get(request_id)
    )

    if driver_group_message:

        group_chat_id = (
            driver_group_message["chat_id"]
        )

        group_message_id = (
            driver_group_message["message_id"]
        )

        print()
        print("=" * 60)
        print("УДАЛЕНИЕ КНОПКИ ИЗ ГРУППЫ ВОДИТЕЛЕЙ")
        print("=" * 60)

        print(
            "GROUP CHAT ID:",
            group_chat_id
        )

        print(
            "MESSAGE ID:",
            group_message_id
        )

        try:

            await callback.bot.edit_message_reply_markup(
                chat_id=group_chat_id,
                message_id=group_message_id,
                reply_markup=None
            )

            print()
            print(
                "✅ КНОПКА «БЕРУ ЗАКАЗ» УДАЛЕНА"
            )

            print(
                "REQUEST ID:",
                request_id
            )

            print(
                "GROUP CHAT ID:",
                group_chat_id
            )

            print(
                "MESSAGE ID:",
                group_message_id
            )

            print("=" * 60)

            driver_order_messages.pop(
                request_id,
                None
            )

        except Exception as error:

            print()
            print(
                "❌ ОШИБКА УДАЛЕНИЯ КНОПКИ "
                "В ГРУППЕ ВОДИТЕЛЕЙ"
            )

            print(
                type(error).__name__,
                repr(error)
            )

    else:

        print()
        print(
            "⚠️ СООБЩЕНИЕ ЗАКАЗА В ГРУППЕ "
            "НЕ НАЙДЕНО В ПАМЯТИ"
        )

        print(
            "REQUEST ID:",
            request_id
        )

    # ========================================================
    # ОТПРАВЛЯЕМ ЗАКАЗ ВОДИТЕЛЮ
    # ========================================================

    driver_text = (
        f"✅ <b>ВАМ НАЗНАЧЕН ЗАКАЗ №{request_id}</b>\n\n"
    )

    if request["ai_summary"]:

        driver_text += (
            f"{request['ai_summary']}\n\n"
        )

    if request["phone"]:

        driver_text += (
            f"📱 <b>Телефон клиента:</b> "
            f"{request['phone']}\n\n"
        )

    driver_text += (
        "Свяжитесь с клиентом и выполните заказ."
    )

    try:

        await callback.bot.send_message(
            selected_driver["driver_id"],
            driver_text,
            parse_mode="HTML"
        )

        print(
            "✅ ДАННЫЕ ЗАКАЗА ОТПРАВЛЕНЫ ВОДИТЕЛЮ"
        )

    except Exception as error:

        print(
            "❌ ОШИБКА ОТПРАВКИ ВОДИТЕЛЮ:",
            repr(error)
        )

    # ========================================================
    # СООБЩЕНИЕ В ГРУППУ
    # ========================================================

    try:

        await callback.bot.send_message(
            group_chat_id
            if driver_group_message
            else callback.message.chat.id,
            f"🔵 <b>ЗАКАЗ №{request_id} НАЗНАЧЕН</b>\n\n"
            f"🚕 Водитель: {driver_name}",
            parse_mode="HTML"
        )

    except Exception as error:

        print(
            "ОШИБКА ОТПРАВКИ В ГРУППУ ВОДИТЕЛЕЙ:",
            repr(error)
        )