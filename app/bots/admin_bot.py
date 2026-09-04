"""
app/bots/admin_bot.py
======================
Admin Bot application factory and handler registration.
"""

from __future__ import annotations

import logging

from telegram import Bot, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.config import get_settings
from app.handlers.admin.approval import (
    approve_callback,
    reject_callback,
    rejection_reason_message,
)
from app.handlers.admin.orders import show_pending_orders
from app.handlers.admin.start import admin_menu_callback, admin_start_handler

logger = logging.getLogger(__name__)

_admin_app: Application | None = None


def build_admin_app() -> Application:
    """Build and configure the Admin Bot Application."""
    global _admin_app
    if _admin_app is not None:
        return _admin_app

    settings = get_settings()
    app = (
        Application.builder()
        .token(settings.admin_bot_token)
        .updater(None)  # Webhook mode — no polling
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", admin_start_handler))

    # Main menu
    app.add_handler(CallbackQueryHandler(admin_menu_callback, pattern=r"^admin:"))

    # Order approve / reject buttons
    app.add_handler(CallbackQueryHandler(approve_callback, pattern=r"^approve:"))
    app.add_handler(CallbackQueryHandler(reject_callback, pattern=r"^reject:"))

    # Admin text input (rejection reason, etc.)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        rejection_reason_message,
    ))

    _admin_app = app
    return app


def get_admin_bot() -> Bot:
    """Return the Admin Bot instance."""
    return build_admin_app().bot


async def process_admin_update(update_data: dict) -> None:
    """Process a raw update dict from the Admin Bot webhook."""
    app = build_admin_app()
    update = Update.de_json(update_data, app.bot)
    await app.process_update(update)
