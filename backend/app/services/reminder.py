"""Daily Telegram follow-up reminders (legacy-bot compatible)."""

from __future__ import annotations

import datetime as dt
import json
import logging
from zoneinfo import ZoneInfo

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app import config
from app.services.sheets import _get_worksheet
from app.services.sheets import sheets_service

logger = logging.getLogger(__name__)


def _parse_date(value: str) -> dt.date | None:
    value = value.strip()
    if not value:
        return None
    for fmt in ("%d.%m.%y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


async def _send_telegram_message(text: str) -> None:
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=15.0) as client:
        for chunk in _split_telegram_text(text):
            res = await client.post(url, json={"chat_id": chat_id, "text": chunk})
            if res.status_code >= 400:
                raise RuntimeError(f"Telegram send failed ({res.status_code}): {res.text}")


def _split_telegram_text(text: str, limit: int = 4000) -> list[str]:
    """Split long messages to stay under Telegram sendMessage limits."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.splitlines():
        candidate = f"{current}\n{line}".strip() if current else line
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = line
            if len(current) <= limit:
                continue
        # Hard split extra-long lines.
        while len(line) > limit:
            chunks.append(line[:limit])
            line = line[limit:]
        current = line

    if current:
        chunks.append(current)
    return chunks


async def daily_followup_check() -> None:
    """Send daily reminders by product timing rules and auto-update system statuses."""
    try:
        ws = _get_worksheet("Pipeline")
        all_values = ws.get_all_values()
    except Exception as exc:
        logger.error("Reminder scheduler: failed to read sheet: %s", exc)
        return

    if len(all_values) < 2:
        logger.info("Reminder scheduler: empty sheet")
        return

    headers = [h.strip() for h in all_values[0]]
    rows = all_values[1:]
    col = {name: idx for idx, name in enumerate(headers)}

    def _val(row: list[str], field: str) -> str:
        idx = col.get(field)
        if idx is None or idx >= len(row):
            return ""
        return str(row[idx]).strip()

    status_col = col.get("Status")

    now = dt.datetime.now(ZoneInfo(config.TIMEZONE))
    today = now.date()
    stale_new: list[str] = []
    followup_1: list[str] = []
    followup_2: list[str] = []
    no_response: list[str] = []
    auto_updates: list[str] = []

    for row_idx, row in enumerate(rows, start=2):
        company = _val(row, "Company") or "?"
        role = _val(row, "Role") or "?"
        status = _val(row, "Status")
        status_low = status.lower()
        applied_date = _parse_date(_val(row, "Applied Date"))
        fu1_date = _parse_date(_val(row, "Follow-up 1"))
        fu2_date = _parse_date(_val(row, "Follow-up 2"))
        response_date = _parse_date(_val(row, "Response Date"))
        created_date = (
            _parse_date(_val(row, "Created Date"))
            or _parse_date(_val(row, "Added Date"))
            or _parse_date(_val(row, "Date Added"))
        )

        # Rule: Stale New = New + 3 days (requires created/added date column).
        if status_low == "new" and created_date and today >= created_date + dt.timedelta(days=3):
            stale_new.append(f"• {company} — {role}")

        if not applied_date:
            continue

        # Rule: No Response = Applied + 30 days (priority over FU reminders).
        if not response_date and today >= applied_date + dt.timedelta(days=30):
            no_response.append(f"• {company} — {role}")
            if status_low in {"applied", "waiting"} and status_col is not None:
                try:
                    ws.update_cell(row_idx, status_col + 1, "No Response")
                    sheets_service.log_event(
                        row_idx,
                        "status_change",
                        json.dumps({"from": status, "to": "No Response"}),
                    )
                    auto_updates.append(f"• {company} — {role}: {status} → No Response")
                    status_low = "no response"
                except Exception as exc:
                    logger.warning("Reminder scheduler: failed to set No Response for row %d: %s", row_idx, exc)
            continue

        # Rule: Follow-up 1 = Applied + 4 days.
        if (
            not response_date
            and not fu1_date
            and today >= applied_date + dt.timedelta(days=4)
            and status_low in {"applied", "waiting"}
        ):
            followup_1.append(f"• {company} — {role}")
            if status_low == "applied" and status_col is not None:
                try:
                    ws.update_cell(row_idx, status_col + 1, "Waiting")
                    sheets_service.log_event(
                        row_idx,
                        "status_change",
                        json.dumps({"from": status, "to": "Waiting"}),
                    )
                    auto_updates.append(f"• {company} — {role}: {status} → Waiting")
                except Exception as exc:
                    logger.warning("Reminder scheduler: failed to set Waiting for row %d: %s", row_idx, exc)

        # Rule: Follow-up 2 = Follow-up 1 + 7 days.
        if (
            not response_date
            and fu1_date
            and not fu2_date
            and today >= fu1_date + dt.timedelta(days=7)
            and status_low in {"applied", "waiting"}
        ):
            followup_2.append(f"• {company} — {role}")

    sheets_service.invalidate_cache()

    sections: list[str] = []
    if stale_new:
        sections.append("🆕 Stale New (New + 3 days):\n" + "\n".join(stale_new))
    if followup_1:
        sections.append("📅 Follow-up 1 (Applied + 4 days):\n" + "\n".join(followup_1))
    if followup_2:
        sections.append("📌 Follow-up 2 (FU1 + 7 days):\n" + "\n".join(followup_2))
    if no_response:
        sections.append("⏳ No Response (Applied + 30 days):\n" + "\n".join(no_response))
    if auto_updates:
        sections.append("⚙️ Auto status updates:\n" + "\n".join(auto_updates))

    msg = "✅ Напоминаний на сегодня нет" if not sections else "\n\n".join(sections)

    try:
        await _send_telegram_message(msg)
        logger.info(
            "Reminder scheduler: sent daily message (stale=%d fu1=%d fu2=%d no_response=%d updates=%d)",
            len(stale_new),
            len(followup_1),
            len(followup_2),
            len(no_response),
            len(auto_updates),
        )
    except Exception as exc:
        logger.error("Reminder scheduler: failed to send Telegram message: %s", exc)


def build_reminder_scheduler() -> AsyncIOScheduler | None:
    """Create scheduler if Telegram config is present."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.info("Reminder scheduler: disabled (missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)")
        return None

    try:
        tz = ZoneInfo(config.TIMEZONE)
    except Exception:
        logger.warning("Reminder scheduler: unknown timezone %r, using Asia/Dubai", config.TIMEZONE)
        tz = ZoneInfo("Asia/Dubai")

    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(
        daily_followup_check,
        trigger="cron",
        hour=config.REMINDER_HOUR,
        minute=config.REMINDER_MINUTE,
    )
    return scheduler


def get_reminder_runtime_status() -> dict:
    return {
        "enabled": bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID),
        "timezone": config.TIMEZONE,
        "hour": config.REMINDER_HOUR,
        "minute": config.REMINDER_MINUTE,
        "telegram_chat_id_configured": bool(config.TELEGRAM_CHAT_ID),
    }
