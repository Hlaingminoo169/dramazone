"""
app/handlers/admin/start.py
=============================
Admin Bot /start command and main menu.
"""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.handlers.admin.auth import is_admin, unauthorized_response

logger = logging.getLogger(__name__)

ADMIN_MENU_TEXT = (
    "👋 <b>DramaZone VIP — Admin Panel</b>\n\n"
    "ဘာလုပ်မည်နည်း?"
)

ADMIN_MENU_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔔 Pending Orders", callback_data="admin:pending")],
    [InlineKeyboardButton("📦 All Orders", callback_data="admin:all_orders")],
    [InlineKeyboardButton("📊 Statistics", callback_data="admin:stats")],
])


async def admin_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — verify admin, show menu."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        await unauthorized_response(update, context)
        return

    await update.message.reply_text(
        ADMIN_MENU_TEXT,
        parse_mode="HTML",
        reply_markup=ADMIN_MENU_KEYBOARD,
    )


async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route main menu callbacks."""
    query = update.callback_query
    user = update.effective_user

    if not user or not is_admin(user.id):
        await unauthorized_response(update, context)
        return

    await query.answer()
    data = query.data

    if data == "admin:pending":
        from app.handlers.admin.orders import show_pending_orders
        await show_pending_orders(update, context)
    elif data == "admin:all_orders":
        from app.handlers.admin.orders import show_all_orders
        await show_all_orders(update, context)
    elif data == "admin:stats":
        from app.handlers.admin.orders import show_statistics
        await show_statistics(update, context)
    elif data == "admin:home":
        await query.edit_message_text(
            ADMIN_MENU_TEXT, parse_mode="HTML", reply_markup=ADMIN_MENU_KEYBOARD
        )
