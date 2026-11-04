from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo
)

MINI_APP_URL = "https://iov1981.github.io/taxi-app/"


def client_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(
                text="🚖 Заказать через приложение",
                web_app=WebAppInfo(url=MINI_APP_URL)
            )
        ],
        [
            KeyboardButton(text="💼 Мой баланс"),
            KeyboardButton(text="ℹ️ Как это работает")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        persistent=True
    )


def admin_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(
                text="🚖 Заказать через приложение",
                web_app=WebAppInfo(url=MINI_APP_URL)
            )
        ],
        [
            KeyboardButton(text="📋 Активные заказы"),
            KeyboardButton(text="📋 Последняя заявка")
        ],
        [
            KeyboardButton(text="📊 Статистика за сегодня"),
            KeyboardButton(text="💼 Мой баланс")
        ],
        [
            KeyboardButton(text="🚗 Водители и авто"),
            KeyboardButton(text="📥 Выгрузить отчёт")
        ],
        [
            KeyboardButton(text="📚 История заказов"),
            KeyboardButton(text="⚙️ Управление тарифами")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        persistent=True
    )