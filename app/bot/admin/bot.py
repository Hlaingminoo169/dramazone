"""
app/bot/admin/bot.py
────────────────────────────────────────────────────────────────────────
Admin Telegram Bot Application Lifecycle & Initialization.

Supports:
- Webhook mode (Production / ngrok)
- Polling mode (Local development)
"""

import logging
import asyncio
from typing import Optional
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler
)

from app.config import config
from app.bot.admin import handlers

logger = logging.getLogger("dramazone.bot.admin")

# Global Application instance for Admin Bot
admin_bot_app: Optional[Application] = None


def create_admin_bot_app() -> Optional[Application]:
    """Initialize and construct the python-telegram-bot Application instance for Admin Bot."""
    token = config.admin_bot_token
    if not token or token == "ADMIN_BOT_TOKEN_HERE":
        logger.warning("ADMIN_BOT_TOKEN is not configured in .env. Admin Bot will not start.")
        return None

    app = Application.builder().token(token).build()

    # Register Admin Commands
    app.add_handler(CommandHandler("start", handlers.admin_start_handler))
    app.add_handler(CommandHandler("admin", handlers.admin_start_handler))
    app.add_handler(CommandHandler("pending", handlers.pending_orders_handler))
    app.add_handler(CommandHandler("movies", handlers.movies_list_handler))

    # Register Callback Query Handlers
    app.add_handler(CallbackQueryHandler(handlers.admin_approve_callback, pattern=r"^admin_approve:.+$"))
    app.add_handler(CallbackQueryHandler(handlers.admin_reject_callback, pattern=r"^admin_reject:.+$"))
    app.add_handler(CallbackQueryHandler(handlers.admin_reject_reason_callback, pattern=r"^admin_reject_reason:.+$"))
    app.add_handler(CallbackQueryHandler(handlers.pending_orders_handler, pattern=r"^admin_view_pending$"))
    app.add_handler(CallbackQueryHandler(handlers.admin_dashboard_refresh_callback, pattern=r"^admin_refresh_dashboard$"))

    logger.info("Admin Bot application successfully configured.")
    return app


async def init_admin_bot() -> None:
    """Initialize Admin Bot application during FastAPI startup."""
    global admin_bot_app
    admin_bot_app = create_admin_bot_app()

    if not admin_bot_app:
        return

    await admin_bot_app.initialize()
    await admin_bot_app.start()

    bot_mode = config.bot_mode.lower()
    if bot_mode == "webhook" and config.webhook_base_url:
        webhook_url = f"{config.webhook_base_url.rstrip('/')}/api/v1/webhook/admin"
        logger.info(f"Setting Admin Bot webhook to: {webhook_url}")
        await admin_bot_app.bot.set_webhook(
            url=webhook_url,
            secret_token=config.webhook_secret or None
        )
    elif bot_mode == "polling":
        logger.info("Starting Admin Bot in POLLING mode for local development...")
        asyncio.create_task(admin_bot_app.updater.start_polling())
    else:
        logger.info(f"Admin bot mode set to '{bot_mode}'. Webhook not set.")


async def stop_admin_bot() -> None:
    """Stop and shutdown Admin Bot application during FastAPI shutdown."""
    global admin_bot_app
    if admin_bot_app:
        logger.info("Stopping Admin Bot application...")
        if admin_bot_app.updater and admin_bot_app.updater.running:
            await admin_bot_app.updater.stop()
        await admin_bot_app.stop()
        await admin_bot_app.shutdown()
        admin_bot_app = None
