import os


def get_admin_id() -> int:
    return int(os.environ["ADMIN_ID"])


def get_drivers_chat_id() -> int:
    return int(os.environ["DRIVERS_CHAT_ID"])