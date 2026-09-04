"""
app/handlers/customer/start.py
================================
Handles /start command and main menu for the Customer Bot.
"""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.database.mongodb import get_db
from app.services.session_service import clear_session
from app.services.user_service import upsert_user
from app.types import BotType

logger = logging.getLogger(__name__)

MAIN_MENU_TEXT = (
    "👋 <b>DramaZone VIP</b> မှ ကြိုဆိုပါသည်!\n\n"
    "🎬 လိုင်စင်ရ မြန်မာဘာသာပြန် ကားများကို VIP Channel မှတဆင့် ကြည့်ရှုနိုင်ပါသည်။\n\n"
    "အောက်ပါ ရွေးချယ်မှုတစ်ခုကို ရွေးချယ်ပါ:"
)

MAIN_MENU_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🎬 VIP ကားဝယ်မည်", callback_data="menu:buy")],
    [InlineKeyboardButton("📦 ကျွန်ုပ်၏ Order များ", callback_data="menu:orders")],
    [InlineKeyboardButton("📞 Admin ကို ဆက်သွယ်မည်", callback_data="menu:contact")],
])


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command — show main menu, upsert user, clear session."""
    user = update.effective_user
    if not user:
        return

    db = get_db()

    # Upsert user record
    upsert_user(db, user)

    # Reset any in-progress session
    clear_session(db, user.id, BotType.CUSTOMER)

    await update.message.reply_text(
        MAIN_MENU_TEXT,
        parse_mode="HTML",
        reply_markup=MAIN_MENU_KEYBOARD,
    )


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle main menu button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data  # e.g. "menu:buy"

    if data == "menu:buy":
        from app.handlers.customer.package import show_packages
        await show_packages(update, context)

    elif data == "menu:orders":
        from app.handlers.customer.orders import show_order_history
        await show_order_history(update, context)

    elif data == "menu:contact":
        from app.handlers.customer.orders import contact_admin
        await contact_admin(update, context)

    else:
        await query.edit_message_text("❓ အမှားတစ်ခု ဖြစ်ပွားသည်။ /start နှိပ်ပါ။")
