import os
from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = int(_get("TELEGRAM_CHAT_ID", "0"))

ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")

GOOGLE_SHEET_ID = _get("GOOGLE_SHEET_ID")
GOOGLE_CREDENTIALS_JSON = _get("GOOGLE_CREDENTIALS_JSON", "./credentials.json")
# Railway: вставь содержимое credentials.json целиком как одну строку
GOOGLE_CREDENTIALS_JSON_CONTENT = _get("GOOGLE_CREDENTIALS_JSON_CONTENT", "")

TIMEZONE = _get("TIMEZONE", "Asia/Dubai")
REMINDER_HOUR = int(_get("REMINDER_HOUR", "8"))
REMINDER_MINUTE = int(_get("REMINDER_MINUTE", "0"))
