"""
app/handlers/customer/package.py

Package selection handler — Step 7.

When the customer taps "🎬 VIP ကားဝယ်မည်", this handler:
1. Shows configured packages as inline buttons.
2. Accepts the selection and stores it in session.
3. Transitions to movie selection.
"""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters, Application

from app.services.session_service import set_session, get_session_data, update_session_data
from app.types import BotType, SessionState
from app.utils.pricing import get_all_packages, format_price, get_package_price, is_valid_package
from app.utils.numbers import parse_myanmar_int

logger = logging.getLogger(__name__)

CB_PKG = "pkg"  # callback prefix: pkg:<quantity>


def _build_package_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard showing all configured packages."""
    buttons = []
    for qty, price in get_all_packages():
        label = f"{qty} ကား — {format_price(price)}"
        if qty == 5:
            label += " 🔥"  # highlight discount
        buttons.append([InlineKeyboardButton(label, callback_data=f"{CB_PKG}:{qty}")])
    return InlineKeyboardMarkup(buttons)


async def show_packages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show package selection menu when user taps the buy button."""
    from app.handlers.customer.start import BTN_BUY

    if update.message and update.message.text == BTN_BUY:
        keyboard = _build_package_keyboard()
        await update.message.reply_text(
            "📦 *Package ရွေးပါ*\n\nဝယ်ယူလိုသော ကားအရေအတွက် ရွေးချယ်ပေးပါ။",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


async def handle_package_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button tap for a package."""
    query = update.callback_query
    await query.answer()

    data = query.data  # e.g. "pkg:3"
    if not data or not data.startswith(f"{CB_PKG}:"):
        return

    try:
        quantity = int(data.split(":")[1])
    except (IndexError, ValueError):
        return

    price = get_package_price(quantity)
    if price is None:
        await query.edit_message_text("❌ ရွေးချယ်မှုမမှန်ကန်ပါ။ ပြန်လည်ကြိုးစားပါ။")
        return

    tg_user = update.effective_user
    # Save package choice in session → transition to movie selection state.
    set_session(
        tg_user.id,
        BotType.CUSTOMER,
        SessionState.SELECTING_MOVIES,
        data={"quantity": quantity, "amount": price, "selectedMovies": []},
    )

    await query.edit_message_text(
        f"✅ *{quantity} ကား — {format_price(price)}* ရွေးချယ်ပြီးပါပြီ။\n\n"
        f"ကောင်းမွန်သော ကားများ ရွေးချယ်ပေးပါ။",
        parse_mode="Markdown",
    )

    # Trigger movie selection immediately.
    from app.handlers.customer.movies import show_movie_selection
    await show_movie_selection(update, context, quantity_override=quantity)


def register(app: Application) -> None:
    """Register package handlers."""
    from app.handlers.customer.start import BTN_BUY

    app.add_handler(
        MessageHandler(filters.Text([BTN_BUY]), show_packages)
    )
    app.add_handler(
        CallbackQueryHandler(handle_package_callback, pattern=f"^{CB_PKG}:")
    )
