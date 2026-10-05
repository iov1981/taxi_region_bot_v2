from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton
)


# ============================================================
# МЕНЮ КЛИЕНТА
# ============================================================

def client_menu():

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📞 Отправить телефон",
                    request_contact=True
                )
            ],
            [
                KeyboardButton(
                    text="ℹ️ Как это работает"
                )
            ]
        ],
        resize_keyboard=True
    )

    return keyboard


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