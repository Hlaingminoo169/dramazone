"""
app/handlers/admin/auth.py
===========================
Admin authorization guard — used by all admin handlers.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.config import get_settings

logger = logging.getLogger(__name__)


def is_admin(telegram_id: int) -> bool:
    """Return True if the Telegram ID is in the authorized admin list."""
    return telegram_id in get_settings().admin_telegram_ids


async def unauthorized_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a generic access-denied message without leaking internal info."""
    text = "🚫 Access Denied.\nYou are not authorized to use this bot."
    if update.message:
        await update.message.reply_text(text)
    elif update.callback_query:
        await update.callback_query.answer(text, show_alert=True)
