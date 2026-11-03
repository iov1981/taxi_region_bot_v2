from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo
)

import os


# ============================================================
# URL MINI APP
# ============================================================

WEBAPP_URL = os.getenv(
    "WEBAPP_URL",
    "https://taxi-region-bot-v2.fadehost.app/webapp/",
).strip()


# ============================================================
# МЕНЮ КЛИЕНТА
# ============================================================

def client_menu():

    keyboard = []

    # --------------------------------------------------------
    # MINI APP
    # --------------------------------------------------------

    if WEBAPP_URL:

        keyboard.append(
            [
                KeyboardButton(
                    text="🚕 Заказать через приложение",
                    web_app=WebAppInfo(
                        url=WEBAPP_URL
                    )
                )
            ]
        )

    # --------------------------------------------------------
    # ТЕЛЕФОН
    # --------------------------------------------------------

    keyboard.append(
        [
            KeyboardButton(
                text="📞 Отправить телефон",
                request_contact=True
            )
        ]
    )

    # --------------------------------------------------------
    # ПОМОЩЬ
    # --------------------------------------------------------

    keyboard.append(
        [
            KeyboardButton(
                text="ℹ️ Как это работает"
            )
        ]
    )

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )


# ============================================================
# МЕНЮ АДМИНИСТРАТОРА
# ============================================================

def admin_menu():

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📋 Последняя заявка"
                )
            ],
            [
                KeyboardButton(
                    text="📋 Активные заказы"
                )
            ],
            [
                KeyboardButton(
                    text="📚 История заказов"
                )
            ],
            [
                KeyboardButton(
                    text="⚙️ Управление тарифами"
                )
            ]
        ],
        resize_keyboard=True
    )

    return keyboard