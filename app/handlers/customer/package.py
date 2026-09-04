"""
app/handlers/customer/package.py
==================================
Package selection and custom quantity entry.
"""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.database.mongodb import get_db
from app.services.session_service import set_session
from app.types import BotType, CustomerState
from app.utils.numbers import normalize_number
from app.utils.pricing import get_pricing_table, get_price_for_quantity

logger = logging.getLogger(__name__)


async def show_packages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show predefined package buttons plus custom quantity option."""
    db = get_db()
    pricing = get_pricing_table(db)

    buttons = [
        [InlineKeyboardButton(item["label"], callback_data=f"pkg:{item['quantity']}")]
        for item in pricing
    ]
    buttons.append([InlineKeyboardButton("🔢 အရေအတွက် ကိုယ်တိုင်ထည့်မည်", callback_data="pkg:custom")])
    buttons.append([InlineKeyboardButton("🏠 မူလစာမျက်နှာ", callback_data="menu:home")])

    text = "🎬 <b>Package ရွေးချယ်ပါ</b>\n\nကြည့်ချင်သော ကားအရေအတွက်ကို ရွေးချယ်ပါ:"

    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))


async def package_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle package selection or custom quantity trigger."""
    query = update.callback_query
    await query.answer()

    data = query.data  # "pkg:1", "pkg:5", "pkg:custom"
    user = update.effective_user
    db = get_db()

    if data == "pkg:custom":
        set_session(db, user.id, BotType.CUSTOMER,
                    state=CustomerState.ENTERING_CUSTOM_QUANTITY.value, data={})
        await query.edit_message_text(
            "🔢 <b>ကားအရေအတွက် ထည့်သွင်းပါ</b>\n\n"
            "ကြည့်ချင်သော ကားအရေအတွက်ကို ရိုက်ထည့်ပါ။\n"
            "မြန်မာဂဏန်း (၁, ၂, ...) သို့မဟုတ် အင်္ဂလိပ်ဂဏန်း (1, 2, ...) အသုံးပြုနိုင်သည်။",
            parse_mode="HTML",
        )
        return

    # Parse quantity from callback data
    try:
        quantity = int(data.split(":")[1])
    except (IndexError, ValueError):
        await query.edit_message_text("❌ မမှန်ကန်သောရွေးချယ်မှု။ /start နှိပ်ပါ။")
        return

    await _proceed_with_quantity(update, context, user.id, quantity)


async def custom_quantity_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text message when user is in ENTERING_CUSTOM_QUANTITY state."""
    user = update.effective_user
    db = get_db()

    from app.services.session_service import get_session
    session = get_session(db, user.id, BotType.CUSTOMER)

    if session.get("state") != CustomerState.ENTERING_CUSTOM_QUANTITY.value:
        return  # Not in this state — ignore

    text = update.message.text or ""
    quantity = normalize_number(text)

    if quantity is None:
        await update.message.reply_text(
            "❌ မမှန်ကန်သောဂဏန်း။ ကျေးဇူးပြု၍ ထပ်မံကြိုးစားပါ။\n"
            "ဥပမာ: 3 သို့မဟုတ် ၃"
        )
        return

    # Check against available movies
    from app.services.movie_service import get_active_movies
    active_movies = get_active_movies(db)
    if quantity > len(active_movies):
        await update.message.reply_text(
            f"❌ လောလောဆယ် ရနိုင်သောကားအရေအတွက်မှာ <b>{len(active_movies)}</b> ကားသာ ရှိသည်။\n"
            f"<b>{len(active_movies)}</b> ထက် နည်းသောအရေအတွက် ထည့်ပါ။",
            parse_mode="HTML",
        )
        return

    await _proceed_with_quantity(update, context, user.id, quantity)


async def _proceed_with_quantity(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    quantity: int,
) -> None:
    """Validate price exists and move to movie selection."""
    db = get_db()
    price = get_price_for_quantity(db, quantity)

    if price is None:
        msg = (
            f"❌ <b>{quantity} ကား</b>အတွက် သတ်မှတ်ထားသောစျေးနှုန်း မရှိသေးပါ။\n\n"
            "Admin ကို ဆက်သွယ်ပါ သို့မဟုတ် အခြားအရေအတွက် ရွေးချယ်ပါ။"
        )
        kbd = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 နောက်သို့", callback_data="menu:buy")
        ]])
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, parse_mode="HTML", reply_markup=kbd)
        else:
            await update.message.reply_text(msg, parse_mode="HTML", reply_markup=kbd)
        return

    # Store quantity and price in session, move to movie selection
    set_session(db, user_id, BotType.CUSTOMER,
                state=CustomerState.SELECTING_MOVIES.value,
                data={"quantity": quantity, "price": price, "selected_movie_ids": []})

    from app.handlers.customer.movies import show_movie_selection
    await show_movie_selection(update, context, user_id, quantity, [], price)
