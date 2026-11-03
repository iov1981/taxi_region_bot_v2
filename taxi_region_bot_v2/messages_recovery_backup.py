import html
import json
from html.parser import HTMLParser
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import (
    Message,
    KeyboardButton,
    ReplyKeyboardMarkup
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import get_admin_id, get_drivers_chat_id

from app.db import (
    create_request,
    save_phone,
    save_admin_message_id,
    get_request
)

from app.services.ai_parser import parse_request
from app.services.route_service import get_route_distance
from app.services.pricing import (
    calculate_trip_price,
    get_trip_type,
    format_price,
)

from app.handlers.start import client_menu


router = Router()

print("messages.py загружен")


# ============================================================
# HTML-ПРОВЕРКА
# ============================================================

class TelegramHTMLValidator(HTMLParser):

    ALLOWED_TAGS = {
        "b",
        "strong",
        "i",
        "em",
        "u",
        "ins",
        "s",
        "strike",
        "del",
        "code",
        "pre",
        "a",
        "tg-spoiler",
        "blockquote",
    }

    def __init__(self):
        super().__init__(
            convert_charrefs=False
        )

        self.errors = []
        self.open_tags = []

    def handle_starttag(
            self,
            tag,
            attrs
    ):
        tag = tag.lower()

        if tag not in self.ALLOWED_TAGS:
            self.errors.append(
                f"Недопустимый HTML-тег: <{tag}>"
            )
            return

        self.open_tags.append(tag)

    def handle_startendtag(
            self,
            tag,
            attrs
    ):
        tag = tag.lower()

        if tag not in self.ALLOWED_TAGS:
            self.errors.append(
                f"Недопустимый HTML-тег: <{tag}/>"
            )