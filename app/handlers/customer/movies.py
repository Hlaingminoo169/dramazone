"""
app/handlers/customer/movies.py
================================
Movie selection with exact-quantity enforcement.
"""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.database.mongodb import get_db
from app.services.movie_service import get_active_movies, get_movies_by_ids
from app.services.session_service import get_session, set_session
from app.types import BotType, CustomerState

logger = logging.getLogger(__name__)


async def show_movie_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    quantity: int,
    selected_ids: list[str],
    price: int,
) -> None:
    """Render the movie selection keyboard with real-time selected count."""
    db = get_db()
    movies = get_active_movies(db)

    selected_count = len(selected_ids)
    header = (
        f"🎬 <b>ကား ရွေးချယ်ပါ</b>\n\n"
        f"ရွေးထားပြီး: <b>{selected_count}/{quantity}</b>\n\n"
        f"ကြည့်ချင်သောကားများကို ရွေးချယ်ပါ:"
    )

    buttons = []
    for movie in movies:
        mid = str(movie["_id"])
        is_selected = mid in selected_ids
        label = ("✅ " if is_selected else "🎬 ") + movie["title"]
        # Toggle: if already selected → deselect, else select
        cb = f"movie:toggle:{mid}"
        buttons.append([InlineKeyboardButton(label, callback_data=cb)])

    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="movie:cancel")])

    markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.edit_message_text(header, parse_mode="HTML", reply_markup=markup)
    else:
        await update.message.reply_text(header, parse_mode="HTML", reply_markup=markup)


async def movie_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle movie select/deselect toggle."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    db = get_db()

    parts = query.data.split(":")  # ["movie", "toggle", "<id>"]
    if len(parts) != 3:
        await query.answer("❌ မမှန်ကန်သောရွေးချယ်မှု။", show_alert=True)
        return

    movie_id = parts[2]

    session = get_session(db, user.id, BotType.CUSTOMER)
    if session.get("state") != CustomerState.SELECTING_MOVIES.value:
        await query.answer("⚠️ Session ကုန်သွားပါပြီ။ /start နှိပ်ပါ။", show_alert=True)
        return

    session_data = session.get("data", {})
    quantity: int = session_data.get("quantity", 0)
    price: int = session_data.get("price", 0)
    selected_ids: list[str] = session_data.get("selected_movie_ids", [])

    # Validate movie exists and is active
    from app.services.movie_service import get_movie_by_id
    movie = get_movie_by_id(db, movie_id)
    if not movie or not movie.get("isActive"):
        await query.answer("❌ ဤကားသည် ရရှိနိုင်ခြင်းမရှိပါ။", show_alert=True)
        return

    if movie_id in selected_ids:
        # Deselect
        selected_ids.remove(movie_id)
    else:
        # Select — check limit
        if len(selected_ids) >= quantity:
            await query.answer(
                f"⚠️ {quantity} ကားသာ ရွေးချယ်နိုင်ပါသည်။", show_alert=True
            )
            return
        selected_ids.append(movie_id)

    # Persist updated selection
    session_data["selected_movie_ids"] = selected_ids
    set_session(db, user.id, BotType.CUSTOMER,
                state=CustomerState.SELECTING_MOVIES.value, data=session_data)

    # Check if selection is complete
    if len(selected_ids) == quantity:
        await _show_order_confirmation(update, context, user.id, quantity, selected_ids, price)
    else:
        await show_movie_selection(update, context, user.id, quantity, selected_ids, price)


async def _show_order_confirmation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    quantity: int,
    selected_ids: list[str],
    price: int,
) -> None:
    """Show order summary after movies are selected."""
    db = get_db()
    movies = get_movies_by_ids(db, selected_ids)

    movie_lines = "\n".join(
        f"  {i+1}. {m.get('title', '?')}" for i, m in enumerate(movies)
    )

    # Generate a temporary order code preview (not saved yet)
    from app.utils.order_code import generate_order_code
    preview_code = generate_order_code()

    # Save confirmation data to session
    session_data = {
        "quantity": quantity,
        "price": price,
        "selected_movie_ids": selected_ids,
        "preview_order_code": preview_code,
    }
    set_session(db, user_id, BotType.CUSTOMER,
                state=CustomerState.CONFIRMING_ORDER.value, data=session_data)

    text = (
        f"📋 <b>Order အတည်ပြုချက်</b>\n\n"
        f"🎬 <b>ရွေးချယ်ထားသောကားများ:</b>\n{movie_lines}\n\n"
        f"🎯 <b>အရေအတွက်:</b> {quantity} ကား\n"
        f"💰 <b>ကျသင့်ငွေ:</b> {price:,} MMK\n\n"
        "ဆက်လက်ဆောင်ရွက်ရန် <b>ငွေပေးချေမည်</b> ကို နှိပ်ပါ။"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 ငွေပေးချေမည်", callback_data="order:confirm")],
        [InlineKeyboardButton("❌ Cancel", callback_data="order:cancel")],
    ])

    query = update.callback_query
    if query:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def movie_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle movie selection cancel."""
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    db = get_db()

    from app.services.session_service import clear_session
    clear_session(db, user.id, BotType.CUSTOMER)

    from app.handlers.customer.start import MAIN_MENU_TEXT, MAIN_MENU_KEYBOARD
    await query.edit_message_text(MAIN_MENU_TEXT, parse_mode="HTML", reply_markup=MAIN_MENU_KEYBOARD)
