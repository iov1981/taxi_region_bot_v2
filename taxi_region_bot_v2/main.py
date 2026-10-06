import asyncio
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from app.db import init_db

from app.handlers.start import router as start_router
from app.handlers.admin import router as admin_router
from app.handlers.drivers import router as drivers_router
from app.handlers.test_order import router as test_order_router
from app.handlers.test_real_order import router as test_real_order_router
from app.handlers.messages import router as messages_router


# ============================================================
# ЗАГРУЗКА .ENV
# ============================================================

load_dotenv()


# ============================================================
# HTTP-СЕРВЕР
# ============================================================

async def health(request):
    return web.Response(
        text="Taxi bot is running"
    )


async def start_web_server():

    app = web.Application()

    app.router.add_get(
        "/",
        health
    )

    app.router.add_get(
        "/health",
        health
    )

    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    runner = web.AppRunner(
        app
    )

    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        port
    )

    await site.start()

    print(
        f"HTTP-сервер запущен на порту {port}"
    )

    return runner


# ============================================================
# TELEGRAM BOT
# ============================================================

async def start_bot():

    token = os.getenv(
        "BOT_TOKEN"
    )

    if not token:
        raise RuntimeError(
            "Не найден BOT_TOKEN"
        )

    admin_id = os.getenv(
        "ADMIN_ID"
    )

    if not admin_id:
        raise RuntimeError(
            "Не найден ADMIN_ID"
        )

    drivers_chat_id = os.getenv(
        "DRIVERS_CHAT_ID"
    )

    if not drivers_chat_id:
        raise RuntimeError(
            "Не найден DRIVERS_CHAT_ID"
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
    # test_order и test_real_order подключаем ДО messages,
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
        test_real_order_router
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
        "Тестовый обработчик /test_real_order подключён."
    )

    print(
        "Порядок routers: "
        "start -> admin -> drivers -> "
        "test_order -> test_real_order -> messages"
    )

    try:

        await dp.start_polling(
            bot
        )

    finally:

        await bot.session.close()


# ============================================================
# MAIN
# ============================================================

async def main():

    # ========================================================
    # HTTP-СЕРВЕР
    # ========================================================

    web_runner = await start_web_server()

    try:

        # ====================================================
        # TELEGRAM POLLING
        # ====================================================

        await start_bot()

    finally:

        await web_runner.cleanup()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )