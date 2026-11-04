import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from app.config import get_bot_token
from app.db import init_db
from app.handlers.admin import router as admin_router
from app.handlers.drivers import router as drivers_router
from app.handlers.messages import router as messages_router


async def main():
    print("Инициализация базы данных...")
    await init_db()

    bot = Bot(token=get_bot_token())
    dp = Dispatcher()

    await bot.set_my_commands([
        BotCommand(command="start", description="Запустить бота / Главное меню"),
        BotCommand(command="balance", description="💼 Баланс и заработок водителя"),
        BotCommand(command="set_car", description="Админ: привязать авто к водителю"),
        BotCommand(command="ban", description="Админ: заблокировать пользователя"),
        BotCommand(command="unban", description="Админ: разблокировать пользователя"),
        BotCommand(command="broadcast_drivers", description="Админ: рассылка водителям"),
        BotCommand(command="broadcast_clients", description="Админ: рассылка клиентам"),
        BotCommand(command="clear_orders", description="Админ: удалить все заказы и обнулить базу"),
    ])

    dp.include_router(admin_router)
    dp.include_router(drivers_router)
    dp.include_router(messages_router)


    print("Запуск бота...")
    print("✅ Бот успешно запущен и ожидает сообщений...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")