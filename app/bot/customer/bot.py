"""
app/bot/customer/bot.py
────────────────────────────────────────────────────────────────────────
Customer Telegram Bot Application Lifecycle & Initialization.

Supports:
- Webhook mode (Production / ngrok local testing)
- Polling mode (Local development without HTTPS)
"""

import logging
import asyncio
from typing import Optional
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from app.config import config
from app.bot.customer import handlers

logger = logging.getLogger("dramazone.bot.customer")

# Global Application instance for Customer Bot
customer_bot_app: Optional[Application] = None


def create_customer_bot_app() -> Optional[Application]:
    """Initialize and construct the python-telegram-bot Application instance."""
    token = config.customer_bot_token
    if not token or token == "CUSTOMER_BOT_TOKEN_HERE":
        logger.warning("CUSTOMER_BOT_TOKEN is not configured in .env. Bot will not start.")
        return None

    app = Application.builder().token(token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", handlers.start_handler))
    app.add_handler(CommandHandler("help", handlers.help_handler))
    app.add_handler(CommandHandler("orders", handlers.orders_handler))
    app.add_handler(CommandHandler("cancel", handlers.cancel_handler))

    # Callback Query Handlers
    app.add_handler(CallbackQueryHandler(handlers.package_select_callback, pattern=r"^pkg:\d+$"))
    app.add_handler(CallbackQueryHandler(handlers.movie_toggle_callback, pattern=r"^toggle:.+$"))
    app.add_handler(CallbackQueryHandler(handlers.confirm_selection_callback, pattern=r"^confirm_selection$"))
    app.add_handler(CallbackQueryHandler(handlers.payment_method_callback, pattern=r"^pay:\w+$"))
    app.add_handler(CallbackQueryHandler(handlers.cancel_order_callback, pattern=r"^cancel_order$"))
    app.add_handler(CallbackQueryHandler(handlers.order_detail_callback, pattern=r"^order_detail:.+$"))

    # Message Handlers
    app.add_handler(MessageHandler(filters.PHOTO, handlers.photo_message_handler))

    logger.info("Customer Bot application successfully configured.")
    return app


async def init_customer_bot() -> None:
    """Initialize bot application during FastAPI startup."""
    global customer_bot_app
    customer_bot_app = create_customer_bot_app()

    if not customer_bot_app:
        return

    await customer_bot_app.initialize()
    await customer_bot_app.start()

    bot_mode = config.bot_mode.lower()
    if bot_mode == "webhook" and config.webhook_base_url:
        webhook_url = f"{config.webhook_base_url.rstrip('/')}/api/v1/webhook/customer"
        logger.info(f"Setting Customer Bot webhook to: {webhook_url}")
        await customer_bot_app.bot.set_webhook(
            url=webhook_url,
            secret_token=config.webhook_secret or None
        )
    elif bot_mode == "polling":
        logger.info("Starting Customer Bot in POLLING mode for local development...")
        # Start updater task in background for polling
        asyncio.create_task(customer_bot_app.updater.start_polling())
    else:
        logger.info(f"Customer bot mode set to '{bot_mode}'. Webhook not automatically set.")


async def stop_customer_bot() -> None:
    """Stop and shutdown bot application during FastAPI shutdown."""
    global customer_bot_app
    if customer_bot_app:
        logger.info("Stopping Customer Bot application...")
        if customer_bot_app.updater and customer_bot_app.updater.running:
            await customer_bot_app.updater.stop()
        await customer_bot_app.stop()
        await customer_bot_app.shutdown()
        customer_bot_app = None
