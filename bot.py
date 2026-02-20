from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import joe
import parser as url_parser
import sheets

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# In-memory state (single-user bot)
# ──────────────────────────────────────────────────────────────────────────────
# user_state[chat_id] = {
#   'result': dict,               # joe.evaluate() output
#   'state': str,                 # 'idle' | 'awaiting_reapply_reason'
#   'max_submission': int,        # filled when duplicate found
# }
user_state: dict[int, dict] = {}


def _add_tracker_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Добавить в трекер", callback_data="add_to_tracker"),
            InlineKeyboardButton("❌ Пропустить", callback_data="skip"),
        ]]
    )


def _reapply_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("Да, повторная подача", callback_data="reapply_yes"),
            InlineKeyboardButton("Нет, отмена", callback_data="reapply_no"),
        ]]
    )


# ──────────────────────────────────────────────────────────────────────────────
# Message handler
# ──────────────────────────────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()

    if not text:
        return

    state = user_state.get(chat_id, {})

    # ── Waiting for reapply reason ──────────────────────────────────────────
    if state.get("state") == "awaiting_reapply_reason":
        reason = text
        result = state["result"]
        result["submission_num"] = state.get("max_submission", 1) + 1
        result["reapply_reason"] = reason

        try:
            sheets.add_row(result)
            user_state.pop(chat_id, None)
            company = result.get("company", "?")
            role = result.get("role", "?")
            sub = result["submission_num"]
            await update.message.reply_text(
                f"✅ Записано как повторная подача #{sub}: {company} — {role}"
            )
        except Exception as exc:
            logger.error("add_row failed: %s", exc)
            await update.message.reply_text(f"❌ Ошибка записи в таблицу: {exc}")
        return

    # ── URL ─────────────────────────────────────────────────────────────────
    if text.startswith("http://") or text.startswith("https://"):
        if "linkedin.com" in text:
            await update.message.reply_text(
                "LinkedIn не читается напрямую. Вставь текст JD сюда — и я оценю."
            )
            return

        await update.message.reply_text("🔍 Читаю страницу…")
        jd_text = url_parser.parse_url(text)
        if not jd_text:
            await update.message.reply_text(
                "❌ Не удалось извлечь текст со страницы. Вставь текст JD вручную."
            )
            return

        await _evaluate_and_reply(update, chat_id, jd_text, source_url=text)
        return

    # ── Long text → treat as JD ─────────────────────────────────────────────
    if len(text) > 200:
        await update.message.reply_text("🤖 Оцениваю вакансию…")
        await _evaluate_and_reply(update, chat_id, text, source_url=None)
        return

    # ── Short text — ignore or prompt ────────────────────────────────────────
    await update.message.reply_text(
        "Пришли ссылку на вакансию или вставь текст JD (от 200 символов)."
    )


async def _evaluate_and_reply(
    update: Update,
    chat_id: int,
    jd_text: str,
    source_url: str | None,
) -> None:
    try:
        result = joe.evaluate(jd_text, source_url=source_url)
    except Exception as exc:
        logger.error("joe.evaluate failed: %s", exc)
        await update.message.reply_text(f"❌ Ошибка оценки: {exc}")
        return

    user_state[chat_id] = {"result": result, "state": "idle", "max_submission": 1}

    msg = joe.format_telegram_message(result)
    await update.message.reply_text(msg, reply_markup=_add_tracker_keyboard())


# ──────────────────────────────────────────────────────────────────────────────
# Callback query handler
# ──────────────────────────────────────────────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    data = query.data
    state = user_state.get(chat_id, {})
    result = state.get("result")

    if data == "skip":
        user_state.pop(chat_id, None)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Ок, пропускаем.")
        return

    if data == "add_to_tracker":
        logger.info("callback add_to_tracker: chat_id=%s, result present=%s", chat_id, bool(result))
        if not result:
            await query.message.reply_text("Нет данных для добавления. Отправь вакансию заново.")
            return

        company = result.get("company", "")
        role = result.get("role", "")
        logger.info("callback add_to_tracker: company=%r role=%r", company, role)

        try:
            logger.info("callback add_to_tracker: calling check_duplicate")
            dup = sheets.check_duplicate(company, role)
            logger.info("callback add_to_tracker: check_duplicate result=%s", dup)
        except Exception as exc:
            logger.error("check_duplicate failed: %s", exc, exc_info=True)
            await query.message.reply_text(f"❌ Ошибка проверки дубля: {exc}")
            return

        if dup["found"]:
            user_state[chat_id]["max_submission"] = dup["max_submission"]
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(
                f"⚠️ Эта вакансия уже в трекере ({company} / {role}).\n"
                "Это повторная подача?",
                reply_markup=_reapply_keyboard(),
            )
        else:
            try:
                logger.info("callback add_to_tracker: no duplicate, calling add_row")
                sheets.add_row(result)
                logger.info("callback add_to_tracker: add_row completed successfully")
                user_state.pop(chat_id, None)
                await query.edit_message_reply_markup(reply_markup=None)
                await query.message.reply_text(
                    f"✅ Добавлено: {company} — {role}"
                )
            except Exception as exc:
                logger.error("add_row failed: %s", exc, exc_info=True)
                await query.message.reply_text(f"❌ Ошибка записи: {exc}")
        return

    if data == "reapply_yes":
        user_state[chat_id]["state"] = "awaiting_reapply_reason"
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Укажи причину повторной подачи:")
        return

    if data == "reapply_no":
        user_state.pop(chat_id, None)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Ок, пропускаем.")
        return


# ──────────────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────────────
def register_handlers(app: Application) -> None:
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
