"""
app/bots/customer_bot.py
=========================
Customer Bot application factory and handler registration.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from telegram import Bot, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.config import get_settings
from app.handlers.customer.approval_redirect import order_action_callback
from app.handlers.customer.movies import movie_cancel_callback, movie_toggle_callback
from app.handlers.customer.orders import contact_admin, show_order_history
from app.handlers.customer.package import package_callback, custom_quantity_message
from app.handlers.customer.payment import (
    order_confirm_callback,
    payment_method_callback,
    screenshot_handler,
)
from app.handlers.customer.start import main_menu_callback, start_handler

logger = logging.getLogger(__name__)

_customer_app: Application | None = None


def build_customer_app() -> Application:
    """Build and configure the Customer Bot Application."""
    global _customer_app
    if _customer_app is not None:
        return _customer_app

    settings = get_settings()
    app = (
        Application.builder()
        .token(settings.customer_bot_token)
        .updater(None)  # Disable polling — we use webhooks
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", start_handler))

    # Main menu callbacks
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern=r"^menu:"))

    # Package selection
    app.add_handler(CallbackQueryHandler(package_callback, pattern=r"^pkg:"))

    # Movie selection
    app.add_handler(CallbackQueryHandler(movie_toggle_callback, pattern=r"^movie:toggle:"))
    app.add_handler(CallbackQueryHandler(movie_cancel_callback, pattern=r"^movie:cancel$"))

    # Order confirm / cancel
    app.add_handler(CallbackQueryHandler(order_confirm_callback, pattern=r"^order:confirm$"))
    app.add_handler(CallbackQueryHandler(order_action_callback, pattern=r"^order:cancel$"))

    # Payment method selection
    app.add_handler(CallbackQueryHandler(payment_method_callback, pattern=r"^pay:"))

    # Text messages — handle state-driven inputs
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        custom_quantity_message,
    ))

    # Photo and image document — payment screenshot
    app.add_handler(MessageHandler(
        filters.PHOTO | (filters.Document.IMAGE),
        screenshot_handler,
    ))

    _customer_app = app
    return app


def get_customer_bot() -> Bot:
    """Return the Customer Bot instance."""
    return build_customer_app().bot


async def process_customer_update(update_data: dict) -> None:
    """Process a raw update dict from the Customer Bot webhook."""
    app = build_customer_app()
    update = Update.de_json(update_data, app.bot)
    await app.process_update(update)
