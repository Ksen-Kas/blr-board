"""Daily Telegram follow-up reminders (legacy-bot compatible)."""

from __future__ import annotations

import datetime as dt
import logging

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


def _parse_event_ts(value: str) -> dt.date | None:
    value = value.strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
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
    """Send daily reminders: FU and stale New/In Progress without activity."""
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

    # Optional activity history from Events sheet.
    last_event_date_by_job: dict[int, dt.date] = {}
    try:
        events_ws = _get_worksheet("Events")
        events_values = events_ws.get_all_values()
        for event_row in events_values[1:]:
            if len(event_row) < 2:
                continue
            try:
                job_id = int(str(event_row[0]).strip())
            except ValueError:
                continue
            event_date = _parse_event_ts(event_row[1])
            if not event_date:
                continue
            prev = last_event_date_by_job.get(job_id)
            if not prev or event_date > prev:
                last_event_date_by_job[job_id] = event_date
    except Exception:
        # Missing worksheet is acceptable; fallback to pipeline date columns.
        pass

    now = dt.datetime.now(ZoneInfo(config.TIMEZONE))
    today = now.date()
    followup_1: list[str] = []
    followup_2: list[str] = []
    stale_work: list[str] = []

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

        if status_low in {"new", "in progress"}:
            last_activity = last_event_date_by_job.get(row_idx) or created_date
            if last_activity and today >= last_activity + dt.timedelta(days=5):
                stale_work.append(
                    f"• #{row_idx} {company} — {role} ({status}, last change {last_activity.isoformat()})"
                )

        if not applied_date:
            continue

        # Rule: Follow-up 1 = Applied + 4 days.
        if (
            not response_date
            and not fu1_date
            and today >= applied_date + dt.timedelta(days=4)
            and status_low in {"applied", "waiting"}
        ):
            followup_1.append(f"• #{row_idx} {company} — {role}")

        # Rule: Follow-up 2 = Follow-up 1 + 7 days.
        if (
            not response_date
            and fu1_date
            and not fu2_date
            and today >= fu1_date + dt.timedelta(days=7)
            and status_low in {"applied", "waiting"}
        ):
            followup_2.append(f"• #{row_idx} {company} — {role}")

    sheets_service.invalidate_cache()

    sections: list[str] = []
    if followup_1:
        sections.append("📅 Follow-up 1 (Applied + 4 days):\n" + "\n".join(followup_1))
    if followup_2:
        sections.append("📌 Follow-up 2 (FU1 + 7 days):\n" + "\n".join(followup_2))
    if stale_work:
        sections.append("🧭 New/In Progress > 5 days without changes:\n" + "\n".join(stale_work))

    msg = "✅ Напоминаний на сегодня нет" if not sections else "\n\n".join(sections)

    try:
        await _send_telegram_message(msg)
        logger.info(
            "Reminder scheduler: sent daily message (fu1=%d fu2=%d stale_work=%d)",
            len(followup_1),
            len(followup_2),
            len(stale_work),
        )
    except Exception as exc:
        logger.error("Reminder scheduler: failed to send Telegram message: %s", exc)


def build_reminder_scheduler() -> AsyncIOScheduler | None:
    """Create scheduler if Telegram config is present."""
    # Temporarily disabled by request: no scheduled Telegram reminders.
    logger.info("Reminder scheduler: disabled by runtime flag (temporary)")
    return None


def get_reminder_runtime_status() -> dict:
    return {
        "enabled": bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID),
        "timezone": config.TIMEZONE,
        "hour": config.REMINDER_HOUR,
        "minute": config.REMINDER_MINUTE,
        "telegram_chat_id_configured": bool(config.TELEGRAM_CHAT_ID),
    }
