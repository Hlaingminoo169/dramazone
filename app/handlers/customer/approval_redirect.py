"""
app/handlers/customer/approval_redirect.py
===========================================
Handles order:cancel callback from order confirmation screen.
Kept separate to avoid circular imports.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.database.mongodb import get_db
from app.services.session_service import clear_session, get_session
from app.types import BotType, CustomerState


async def order_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle order:cancel from the confirmation screen."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    db = get_db()

    session = get_session(db, user.id, BotType.CUSTOMER)
    session_data = session.get("data", {})
    order_code = session_data.get("order_code")

    if order_code:
        from app.services.order_service import cancel_order
        cancel_order(db, order_code, user.id)

    clear_session(db, user.id, BotType.CUSTOMER)

    from app.handlers.customer.start import MAIN_MENU_TEXT, MAIN_MENU_KEYBOARD
    await query.edit_message_text(
        "❌ Order ပယ်ဖျက်လိုက်ပါပြီ။\n\n" + MAIN_MENU_TEXT,
        parse_mode="HTML",
        reply_markup=MAIN_MENU_KEYBOARD,
    )
