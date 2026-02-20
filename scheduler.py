from __future__ import annotations

import datetime
import logging

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot

import config
import sheets

logger = logging.getLogger(__name__)


async def daily_followup_check(bot: Bot, chat_id: int) -> None:
    """Send follow-up reminders for today's dates."""
    try:
        sheet = sheets.get_sheet()
        rows = sheet.get_all_records()
    except Exception as exc:
        logger.error("Scheduler: failed to read sheet: %s", exc)
        return

    today = datetime.date.today()
    reminders: list[str] = []

    for row in rows:
        for col in ("Follow-up 1", "Follow-up 2"):
            date_str = str(row.get(col, "")).strip()
            if not date_str:
                continue
            try:
                d = datetime.datetime.strptime(date_str, "%d.%m.%y").date()
                if d == today:
                    reminders.append(f"• {row.get('Company', '?')} — {row.get('Role', '?')} [{col}]")
            except ValueError:
                pass

    if reminders:
        msg = "📅 Follow-up сегодня:\n\n" + "\n".join(reminders)
    else:
        msg = "✅ Follow-up на сегодня нет"

    try:
        await bot.send_message(chat_id=chat_id, text=msg)
    except Exception as exc:
        logger.error("Scheduler: failed to send message: %s", exc)


def build_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    try:
        tz = pytz.timezone(config.TIMEZONE)
    except Exception:
        logger.warning(
            "Unknown timezone %r, falling back to Asia/Dubai", config.TIMEZONE
        )
        tz = pytz.timezone("Asia/Dubai")

    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(
        daily_followup_check,
        trigger="cron",
        hour=config.REMINDER_HOUR,
        minute=config.REMINDER_MINUTE,
        kwargs={"bot": bot, "chat_id": config.TELEGRAM_CHAT_ID},
    )
    return scheduler
