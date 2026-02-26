"""Config — shares the same env vars as the Telegram bot."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


# Claude API
ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")

# Google Sheets — same credentials as the Telegram bot
GOOGLE_SHEET_ID = _get("GOOGLE_SHEET_ID")
GOOGLE_CREDENTIALS_JSON_CONTENT = _get("GOOGLE_CREDENTIALS_JSON_CONTENT")

# Paths
CLIENT_SPACE_PATH = _get(
    "CLIENT_SPACE_PATH",
    str(Path(__file__).resolve().parent.parent.parent / "CLIENT_SPACE"),
)

# Canon fallback (for environments where CLIENT_SPACE files are not mounted)
CANONICAL_RESUME_CONTENT = _get("CANONICAL_RESUME_CONTENT")
CANON_STRATEGY_CONTENT = _get("CANON_STRATEGY_CONTENT")
CANON_LETTER_RULES_CONTENT = _get("CANON_LETTER_RULES_CONTENT")

# Telegram (for reference / future webhook integration)
TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = int(_get("TELEGRAM_CHAT_ID", "0"))

# Runtime environment
APP_ENV = _get("APP_ENV", "development").lower()

# Access control
API_ACCESS_USERNAME = _get("API_ACCESS_USERNAME")
API_ACCESS_PASSWORD = _get("API_ACCESS_PASSWORD")
INTERNAL_API_KEY = _get("INTERNAL_API_KEY")

# CORS
ALLOWED_ORIGINS = [o.strip() for o in _get("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
