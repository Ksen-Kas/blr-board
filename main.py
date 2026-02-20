import logging

from telegram.ext import Application

import config
import bot as joe_bot
import scheduler as sched

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(app: Application) -> None:
    """Called by python-telegram-bot after the event loop is running."""
    scheduler = sched.build_scheduler(app.bot)
    scheduler.start()
    logger.info(
        "Scheduler started — daily check at %02d:%02d (%s)",
        config.REMINDER_HOUR,
        config.REMINDER_MINUTE,
        config.TIMEZONE,
    )


def main() -> None:
    logger.info("Starting Joe Bot…")

    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    joe_bot.register_handlers(app)

    logger.info("Polling…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
