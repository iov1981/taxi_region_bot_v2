import asyncio
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from app.db import init_db

from app.handlers.start import router as start_router
from app.handlers.admin import router as admin_router
from app.handlers.drivers import router as drivers_router
from app.handlers.test_order import router as test_order_router
from app.handlers.messages import router as messages_router


# ============================================================
# ЗАГРУЗКА .ENV
# ============================================================

load_dotenv(
    "G:/taxi_region_bot_v2/.env"
)


# ============================================================
# MAIN
# ============================================================

async def main():

    token = os.getenv("BOT_TOKEN")

    if not token:
        raise RuntimeError(
            "Не найден BOT_TOKEN в .env"
        )

    admin_id = os.getenv("ADMIN_ID")

    if not admin_id:
        raise RuntimeError(
            "Не найден ADMIN_ID в .env"
        )

    drivers_chat_id = os.getenv("DRIVERS_CHAT_ID")

    if not drivers_chat_id:
        raise RuntimeError(
            "Не найден DRIVERS_CHAT_ID в .env"
        )

    print(
        "ADMIN_ID:",
        admin_id
    )

    print(
        "DRIVERS_CHAT_ID:",
        drivers_chat_id
    )

    # ========================================================
    # БАЗА ДАННЫХ
    # ========================================================

    await init_db()

    # ========================================================
    # BOT
    # ========================================================

    bot = Bot(
        token=token
    )

    # ========================================================
    # DISPATCHER
    # ========================================================

    dp = Dispatcher()

    # ========================================================
    # ROUTERS
    #
    # ВАЖНО:
    # test_order подключаем ДО messages,
    # потому что messages обрабатывает обычный текст.
    # ========================================================

    dp.include_router(
        start_router
    )

    dp.include_router(
        admin_router
    )

    dp.include_router(
        drivers_router
    )

    dp.include_router(
        test_order_router
    )

    dp.include_router(
        messages_router
    )

    # ========================================================
    # ЗАПУСК
    # ========================================================

    print(
        "Бот запущен."
    )

    print(
        "Тестовый обработчик /test_order подключён."
    )

    print(
        "Порядок routers: start -> admin -> drivers -> test_order -> messages"
    )

    await dp.start_polling(
        bot
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())