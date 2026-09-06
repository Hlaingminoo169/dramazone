"""
app/handlers/customer/start.py

Customer Bot /start handler — Step 6.

Saves/updates user profile in MongoDB.
Shows the main menu.
"""
from __future__ import annotations

import logging

from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import CommandHandler, ContextTypes, Application

from app.services.user_service import upsert_user
from app.services.session_service import clear_session
from app.types import BotType

logger = logging.getLogger(__name__)

# ── Menu button labels ────────────────────────────────────────────────────────
BTN_BUY = "🎬 VIP ကားဝယ်မည်"
BTN_ORDERS = "📦 ကျွန်ုပ်၏ Order များ"
BTN_CONTACT = "📞 Admin ကို ဆက်သွယ်မည်"

MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton(BTN_BUY)], [KeyboardButton(BTN_ORDERS)], [KeyboardButton(BTN_CONTACT)]],
    resize_keyboard=True,
    one_time_keyboard=False,
)

WELCOME_TEXT = (
    "🎬 *DramaZone VIP မှ ကြိုဆိုပါတယ်*\n\n"
    "VIP Content ဝယ်ယူရန် အောက်ပါ Menu ကို အသုံးပြုနိုင်ပါတယ်။"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — upsert user, clear stale session, show main menu."""
    tg_user = update.effective_user
    if tg_user is None:
        return

    # Save / update user profile.
    upsert_user(tg_user)

    # Clear any existing session so the user starts fresh.
    clear_session(tg_user.id, BotType.CUSTOMER)

    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=MAIN_MENU_KEYBOARD,
    )
    logger.info("User %s started customer bot.", tg_user.id)


def register(app: Application) -> None:
    """Register start handler on the Application."""
    app.add_handler(CommandHandler("start", start))
