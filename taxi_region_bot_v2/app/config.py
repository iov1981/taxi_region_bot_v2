import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
DRIVERS_CHAT_ID = int(os.getenv("DRIVERS_CHAT_ID", 0))
SERVICE_COMMISSION_PERCENT = int(os.getenv("SERVICE_COMMISSION_PERCENT", 10))


def get_bot_token() -> str:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан в файле .env!")
    return BOT_TOKEN


def get_admin_id() -> int:
    return ADMIN_ID


def get_drivers_chat_id() -> int:
    return DRIVERS_CHAT_ID


def get_commission_percent() -> int:
    return SERVICE_COMMISSION_PERCENT