"""
app/handlers/admin/start.py

Admin Bot /start handler — Step 12.

Only authorised admin Telegram IDs can access this bot.
"""
from __future__ import annotations

import logging

from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import settings
from app.services.session_service import clear_session
from app.types import BotType

logger = logging.getLogger(__name__)

ADMIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🔔 Pending Orders"), KeyboardButton("📦 All Orders")],
        [KeyboardButton("📊 Statistics"), KeyboardButton("📋 Audit Log")],
    ],
    resize_keyboard=True,
)

DENIED_TEXT = (
    "🚫 ဤ Bot ကို သင်အသုံးပြုခွင့် မရှိပါ။\n\n"
    "Authorised admins only."
)


async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start for the admin bot."""
    tg_user = update.effective_user
    if tg_user is None:
        return

    if not settings.is_admin(tg_user.id):
        logger.warning("Unauthorised /start attempt by user %s", tg_user.id)
        await update.message.reply_text(DENIED_TEXT)
        return

    clear_session(tg_user.id, BotType.ADMIN)
    await update.message.reply_text(
        f"👋 *DramaZone VIP Admin Panel*\n\nကြိုဆိုပါတယ်၊ {tg_user.first_name}!\n\nMenu မှ ရွေးချယ်ပေးပါ။",
        parse_mode="Markdown",
        reply_markup=ADMIN_MENU_KEYBOARD,
    )


def register(app: Application) -> None:
    app.add_handler(CommandHandler("start", admin_start))
