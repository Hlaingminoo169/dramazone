"""
app/handlers/customer/movies.py

Movie selection handler — Step 9.

Displays active movies as an inline keyboard.
Customers can select/deselect movies up to the required quantity.
When done, shows confirmation with total price.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, Application

from app.services.movie_service import get_active_movies, get_movies_by_ids
from app.services.session_service import get_session, set_session, update_session_data
from app.types import BotType, SessionState
from app.utils.pricing import format_price

logger = logging.getLogger(__name__)

CB_MOVIE = "mov"        # mov:<movie_id>
CB_CONFIRM = "mov_ok"   # confirm movie selection
CB_CANCEL = "mov_cancel"


def _build_movie_keyboard(
    movies: list,
    selected_ids: List[str],
    required: int,
) -> InlineKeyboardMarkup:
    """
    Build movie selection keyboard.

    Selected movies show ✅ prefix.
    When enough movies are selected, show Confirm button.
    Always show Cancel button.
    """
    buttons = []
    for movie in movies:
        mid = str(movie["_id"])
        tick = "✅ " if mid in selected_ids else ""
        buttons.append([
            InlineKeyboardButton(
                f"{tick}{movie['title']}",
                callback_data=f"{CB_MOVIE}:{mid}",
            )
        ])

    count = len(selected_ids)
    action_row = []
    if count == required:
        action_row.append(
            InlineKeyboardButton("💳 ငွေပေးချေမည်", callback_data=CB_CONFIRM)
        )
    action_row.append(
        InlineKeyboardButton("❌ Cancel", callback_data=CB_CANCEL)
    )
    buttons.append(action_row)

    return InlineKeyboardMarkup(buttons)


async def show_movie_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    quantity_override: Optional[int] = None,
) -> None:
    """Display the movie selection keyboard."""
    tg_user = update.effective_user
    session = get_session(tg_user.id, BotType.CUSTOMER)
    if not session or session.get("state") != SessionState.SELECTING_MOVIES:
        return

    data = session.get("data", {})
    quantity = quantity_override or data.get("quantity", 1)
    selected_ids: List[str] = data.get("selectedMovies", [])

    movies = get_active_movies()
    if not movies:
        msg = "⚠️ ယခုအချိန်တွင် ရရှိနိုင်သော ကားများ မရှိသေးပါ။ ခဏကြာပြီးနောက် ပြန်ကြိုးစားပါ။"
        if update.callback_query:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return

    keyboard = _build_movie_keyboard(movies, selected_ids, quantity)
    text = (
        f"🎬 *ကားရွေးပါ*\n\n"
        f"ရွေးထားပြီး: {len(selected_ids)}/{quantity}"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=keyboard
        )
    else:
        await update.effective_message.reply_text(
            text, parse_mode="Markdown", reply_markup=keyboard
        )


async def handle_movie_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle movie toggle (select / deselect)."""
    query = update.callback_query
    await query.answer()
    tg_user = update.effective_user

    session = get_session(tg_user.id, BotType.CUSTOMER)
    if not session or session.get("state") != SessionState.SELECTING_MOVIES:
        await query.edit_message_text(
            "⚠️ Session သက်တမ်းကုန်သွားပါပြီ။ /start ကိုနှိပ်ပြီး ပြန်စပါ။"
        )
        return

    data = session.get("data", {})
    quantity: int = data.get("quantity", 1)
    selected_ids: List[str] = data.get("selectedMovies", [])

    # Parse movie_id from callback.
    raw = query.data  # "mov:<movie_id>"
    movie_id = raw.split(":")[1] if ":" in raw else None
    if not movie_id:
        return

    if movie_id in selected_ids:
        # Deselect.
        selected_ids.remove(movie_id)
    else:
        if len(selected_ids) >= quantity:
            await query.answer(
                f"ကား {quantity} ခုသာ ရွေးနိုင်ပါသည်။", show_alert=True
            )
            return
        # Verify movie is still active.
        movies = get_movies_by_ids([movie_id])
        if not movies:
            await query.answer("ဤကားသည် ရရှိ၍မရပါ။", show_alert=True)
            return
        selected_ids.append(movie_id)

    update_session_data(tg_user.id, BotType.CUSTOMER, {"selectedMovies": selected_ids})

    # Refresh the keyboard.
    movies = get_active_movies()
    keyboard = _build_movie_keyboard(movies, selected_ids, quantity)
    text = (
        f"🎬 *ကားရွေးပါ*\n\n"
        f"ရွေးထားပြီး: {len(selected_ids)}/{quantity}"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def handle_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle movie selection confirmation → show order summary."""
    query = update.callback_query
    await query.answer()
    tg_user = update.effective_user

    session = get_session(tg_user.id, BotType.CUSTOMER)
    if not session or session.get("state") != SessionState.SELECTING_MOVIES:
        await query.edit_message_text("⚠️ Session သက်တမ်းကုန်သွားပါပြီ။ /start ကိုနှိပ်ပါ။")
        return

    data = session.get("data", {})
    quantity: int = data.get("quantity", 1)
    amount: int = data.get("amount", 0)
    selected_ids: List[str] = data.get("selectedMovies", [])

    if len(selected_ids) != quantity:
        await query.answer(
            f"ကား {quantity} ခု ရွေးရပါမည်။ ({len(selected_ids)} ခုသာ ရွေးထားသည်)",
            show_alert=True,
        )
        return

    # Fetch snapshots — validate all IDs are still active.
    movies = get_movies_by_ids(selected_ids)
    if len(movies) != quantity:
        await query.edit_message_text(
            "⚠️ ရွေးချယ်ထားသော ကားများ တချို့မရရှိနိုင်တော့ပါ။ ပြန်လည်ရွေးချယ်ပေးပါ။"
        )
        return

    # Reorder movies to match selected order.
    id_to_movie = {str(m["_id"]): m for m in movies}
    ordered_movies = [id_to_movie[mid] for mid in selected_ids if mid in id_to_movie]

    movie_snapshots = [
        {
            "movieId": str(m["_id"]),
            "title": m["title"],
            "channelLink": m["channelLink"],
        }
        for m in ordered_movies
    ]

    # Store snapshots in session and transition state.
    set_session(
        tg_user.id,
        BotType.CUSTOMER,
        SessionState.SELECTING_PAYMENT,
        data={
            "quantity": quantity,
            "amount": amount,
            "movieSnapshots": movie_snapshots,
        },
    )

    # Build confirmation message.
    movie_list = "\n".join(
        f"{i + 1}. {m['title']}" for i, m in enumerate(ordered_movies)
    )
    text = (
        f"🎬 *ရွေးထားသောကားများ*\n\n"
        f"{movie_list}\n\n"
        f"စုစုပေါင်း: *{format_price(amount)}*"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 ငွေပေးချေမည်", callback_data="pay_select")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_order")],
    ])

    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def handle_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel current flow and return to start."""
    from app.services.session_service import clear_session
    from app.handlers.customer.start import MAIN_MENU_KEYBOARD

    query = update.callback_query
    await query.answer()
    tg_user = update.effective_user
    clear_session(tg_user.id, BotType.CUSTOMER)

    await query.edit_message_text("❌ ပယ်ဖျက်ပြီးပါပြီ။")
    await context.bot.send_message(
        chat_id=tg_user.id,
        text="🏠 Main Menu သို့ ပြန်သွားပါ။",
        reply_markup=MAIN_MENU_KEYBOARD,
    )


def register(app: Application) -> None:
    """Register movie selection handlers."""
    app.add_handler(CallbackQueryHandler(handle_movie_callback, pattern=f"^{CB_MOVIE}:"))
    app.add_handler(CallbackQueryHandler(handle_confirm_callback, pattern=f"^{CB_CONFIRM}$"))
    app.add_handler(CallbackQueryHandler(handle_cancel_callback, pattern="^cancel_order$"))
