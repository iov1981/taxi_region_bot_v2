from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from app.config import get_admin_id
from app.keyboards import client_menu, admin_menu

router = Router()


@router.message(CommandStart())
async def start(message: Message):

    # ============================================================
    # АДМИНИСТРАТОР
    # Админ-меню показываем ТОЛЬКО в личном чате с ботом.
    # В группе водителей админ-меню НЕ показываем.
    # ============================================================
    if message.from_user.id == get_admin_id():

        if message.chat.type == "private":
            await message.answer(
                "👑 Вы вошли как администратор.\n\n"
                "Новые сообщения клиентов будут приходить сюда.",
                reply_markup=admin_menu(),
            )

        return

    # ============================================================
    # КЛИЕНТ
    # ============================================================
    await message.answer(
        "🚕 Поездки по Пензенской области, Саратовской области "
        "и Мордовии.\n\n"
        "Просто напишите направление обычным сообщением.\n"
        "Например:\n"
        "«Пенза — Саратов, 2 человека, завтра утром»",
        reply_markup=client_menu(),
    )


@router.message(Command("chatid"))
async def chat_id(message: Message):

    await message.answer(
        f"🆔 ID этого чата:\n\n"
        f"`{message.chat.id}`",
        parse_mode="Markdown"
    )


@router.message(lambda m: m.text == "ℹ️ Как это работает")
async def how_it_works(message: Message):

    await message.answer(
        "Напишите откуда и куда едете. Можно добавить дату, "
        "время и количество пассажиров. Администратор получит заявку "
        "и свяжется с вами."
    )