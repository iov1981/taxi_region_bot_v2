import asyncio
import os
from pathlib import Path

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
# ПУТЬ К MINI APP
# ============================================================

WEBAPP_PATH = (
    Path(__file__).resolve().parent / "webapp"
)


# ============================================================
# HEALTH CHECK
# ============================================================

async def health(request):

    return web.Response(
        text="Taxi bot is running"
    )


# ============================================================
# MINI APP — INDEX
# ============================================================

async def webapp_index(request):

    index_file = WEBAPP_PATH / "index.html"

    if not index_file.exists():

        return web.Response(
            text="Mini App index.html not found",
            status=500
        )

    return web.FileResponse(
        index_file
    )


# ============================================================
# MINI APP — INDEX.HTML
# ============================================================

async def webapp_index_file(request):

    index_file = WEBAPP_PATH / "index.html"

    if not index_file.exists():

        return web.Response(
            text="Mini App index.html not found",
            status=500
        )

    return web.FileResponse(
        index_file
    )


# ============================================================
# MINI APP — CSS
# ============================================================

async def webapp_css(request):

    css_file = WEBAPP_PATH / "style.css"

    if not css_file.exists():

        return web.Response(
            text="Mini App style.css not found",
            status=500
        )

    return web.FileResponse(
        css_file
    )


# ============================================================
# MINI APP — JAVASCRIPT
# ============================================================

async def webapp_js(request):

    js_file = WEBAPP_PATH / "app.js"

    if not js_file.exists():

        return web.Response(
            text="Mini App app.js not found",
            status=500
        )

    return web.FileResponse(
        js_file
    )


# ============================================================
# HTTP-СЕРВЕР
# ============================================================

async def start_web_server():

    # ========================================================
    # ПРОВЕРКА ПАПКИ MINI APP
    # ========================================================

    if not WEBAPP_PATH.exists():

        raise RuntimeError(
            f"Папка Mini App не найдена: {WEBAPP_PATH}"
        )

    # ========================================================
    # ПРОВЕРКА ФАЙЛОВ
    # ========================================================

    index_file = WEBAPP_PATH / "index.html"
    css_file = WEBAPP_PATH / "style.css"
    js_file = WEBAPP_PATH / "app.js"

    if not index_file.exists():

        raise RuntimeError(
            f"Файл Mini App не найден: {index_file}"
        )

    if not css_file.exists():

        raise RuntimeError(
            f"Файл Mini App не найден: {css_file}"
        )

    if not js_file.exists():

        raise RuntimeError(
            f"Файл Mini App не найден: {js_file}"
        )

    # ========================================================
    # WEB APPLICATION
    # ========================================================

    app = web.Application()

    # ========================================================
    # HEALTH
    # ========================================================

    app.router.add_get(
        "/health",
        health
    )

    # ========================================================
    # MINI APP
    # ========================================================

    app.router.add_get(
        "/webapp/",
        webapp_index
    )

    app.router.add_get(
        "/webapp/index.html",
        webapp_index_file
    )

    # ========================================================
    # CSS
    # ========================================================

    app.router.add_get(
        "/webapp/style.css",
        webapp_css
    )

    # ========================================================
    # JAVASCRIPT
    # ========================================================

    app.router.add_get(
        "/webapp/app.js",
        webapp_js
    )

    # ========================================================
    # ГЛАВНАЯ СТРАНИЦА
    # ========================================================

    app.router.add_get(
        "/",
        health
    )

    # ========================================================
    # PORT
    # ========================================================

    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    # ========================================================
    # RUNNER
    # ========================================================

    runner = web.AppRunner(
        app
    )

    await runner.setup()

    # ========================================================
    # TCP SITE
    # ========================================================

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        port
    )

    await site.start()

    print(
        f"HTTP-сервер запущен на порту {port}"
    )

    print(
        "Mini App:"
    )

    print(
        "  /webapp/"
    )

    print(
        "  /webapp/index.html"
    )

    print(
        "  /webapp/style.css"
    )

    print(
        "  /webapp/app.js"
    )

    return runner


# ============================================================
# TELEGRAM BOT
# ============================================================

async def start_bot():

    # ========================================================
    # BOT TOKEN
    # ========================================================

    token = os.getenv(
        "BOT_TOKEN"
    )

    if not token:

        raise RuntimeError(
            "Не найден BOT_TOKEN"
        )

    # ========================================================
    # ADMIN ID
    # ========================================================

    admin_id = os.getenv(
        "ADMIN_ID"
    )

    if not admin_id:

        raise RuntimeError(
            "Не найден ADMIN_ID"
        )

    # ========================================================
    # DRIVERS CHAT ID
    # ========================================================

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

    # ========================================================
    # POLLING
    # ========================================================

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
        # TELEGRAM BOT
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