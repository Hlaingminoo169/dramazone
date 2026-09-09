"""
app/bot/customer/handlers.py
────────────────────────────────────────────────────────────────────────
Customer Telegram Bot Command & Callback Handlers.

Handles:
- /start: Register user, show package selection / movie catalog
- /orders: Show user order history
- /cancel: Cancel draft order / reset session
- /help: Show help message
- Callback queries:
  - pkg:<size> -> Select package size (1, 3, 5)
  - toggle:<movie_id> -> Toggle movie selection
  - confirm_selection -> Create draft order & ask payment method
  - pay:<method> -> Select payment method & show payment details
  - cancel_order -> Cancel order setup
  - order_detail:<order_code> -> View specific order detail
- Photo messages: Payment screenshot submission
"""

import logging
from typing import List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.config import get_settings
from app.models.session import SessionState
from app.services.session_service import session_service
from app.services.user_service import user_service
from app.services.movie_service import movie_service
from app.services.order_service import order_service
from app.services.rate_limit_service import rate_limit_service

config = get_settings()
from app.bot.customer import messages

logger = logging.getLogger("dramazone.bot.customer")


async def rate_limit_check(update: Update, action_key: str, limit: int = 10, window: int = 60) -> bool:
    """Helper to check rate limit for Telegram user."""
    user = update.effective_user
    if not user:
        return True
    
    is_allowed = await rate_limit_service.check_rate_limit(
        identifier=str(user.id),
        action_key=action_key,
        limit=limit,
        window_seconds=window
    )
    if not is_allowed:
        if update.callback_query:
            await update.callback_query.answer(messages.RATE_LIMIT_EXCEEDED, show_alert=True)
        elif update.message:
            await update.message.reply_text(messages.RATE_LIMIT_EXCEEDED)
        return False
    return True


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not update.effective_user or not update.message:
        return
        
    user = update.effective_user
    if not await rate_limit_check(update, "cmd_start"):
        return

    # Upsert user in DB
    await user_service.upsert_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    # Reset/clear active session
    await session_service.clear_session(user.id)

    # Send welcome message & Package Selection Keyboard
    keyboard = [
        [
            InlineKeyboardButton("1 ကား (1,500 MMK)", callback_data="pkg:1"),
        ],
        [
            InlineKeyboardButton("3 ကား (3,500 MMK)", callback_data="pkg:3"),
        ],
        [
            InlineKeyboardButton("5 ကား (5,000 MMK)", callback_data="pkg:5"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        messages.WELCOME,
        reply_markup=reply_markup
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not update.message:
        return
    await update.message.reply_text(messages.HELP_TEXT)


async def orders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /orders command - list user's active/past orders."""
    if not update.effective_user or not update.message:
        return
        
    user = update.effective_user
    if not await rate_limit_check(update, "cmd_orders"):
        return

    orders = await order_service.get_user_orders(telegram_id=user.id, limit=10)
    if not orders:
        await update.message.reply_text(messages.NO_ORDERS_FOUND)
        return

    text = "📋 **သင်၏ Order များ**\n\n"
    keyboard = []
    for order in orders:
        status_str = messages.STATUS_LABELS.get(order.status, order.status.value)
        text += f"• Order #{order.orderCode} — {status_str} ({order.totalPrice:,} MMK)\n"
        keyboard.append([InlineKeyboardButton(f"Order #{order.orderCode} အသေးစိတ်ကြည့်ရန်", callback_data=f"order_detail:{order.orderCode}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel command."""
    if not update.effective_user or not update.message:
        return

    user = update.effective_user
    session = await session_service.get_session(user.id)

    if session and session.activeOrderId:
        await order_service.cancel_order(
            order_id=session.activeOrderId,
            telegram_id=user.id,
            reason="Cancelled by user command"
        )

    await session_service.clear_session(user.id)
    await update.message.reply_text(messages.ORDER_CANCELLED)


async def package_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle package size selection callback (pkg:1, pkg:3, pkg:5)."""
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()

    if not await rate_limit_check(update, "cb_pkg"):
        return

    user = update.effective_user
    data = query.data or ""
    pkg_size = int(data.split(":")[1])

    if pkg_size not in config.available_package_sizes:
        await query.edit_message_text(messages.INVALID_PACKAGE_SIZE)
        return

    # Update session to SELECTING_PACKAGE
    await session_service.set_state(
        telegram_id=user.id,
        state=SessionState.SELECTING_PACKAGE,
        package_size=pkg_size,
        selected_movie_ids=[]
    )

    # Show available movies
    await show_movie_selection_grid(query, user.id, pkg_size, [])


async def show_movie_selection_grid(query_or_update, telegram_id: int, pkg_size: int, selected_ids: List[str]) -> None:
    """Render movie catalog selection grid with checkboxes."""
    movies = await movie_service.get_active_movies()
    if not movies:
        msg = "လတ်တလော ကြည့်ရှုနိုင်သော ဇာတ်ကားများ မရှိသေးပါ။ ကျေးဇူးပြု၍ နောက်မှ ပြန်လည် ကြိုးစားပါ။"
        if hasattr(query_or_update, "edit_message_text"):
            await query_or_update.edit_message_text(msg)
        else:
            await query_or_update.message.reply_text(msg)
        return

    price = config.package_prices.get(pkg_size, 0)
    
    text = (
        f"🎬 **ဇာတ်ကား ရွေးချယ်ရန်**\n\n"
        f"• ရွေးချယ်ထားသော ပက်ကေ့ဂျ်: **{pkg_size} ကား ({price:,} MMK)**\n"
        f"• ရွေးချယ်ပြီး အရေအတွက်: **{len(selected_ids)} / {pkg_size}**\n\n"
        f"အောက်ပါ ဇာတ်ကားများထဲမှ **{pkg_size} ကား** ကို နှိပ်၍ ရွေးချယ်ပါ။"
    )

    keyboard = []
    for m in movies:
        m_id = str(m.id)
        is_selected = m_id in selected_ids
        check_mark = "✅ " if is_selected else "➕ "
        button_text = f"{check_mark}{m.titleMM or m.titleEn}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"toggle:{m_id}")])

    # Action buttons
    action_row = []
    if len(selected_ids) == pkg_size:
        action_row.append(InlineKeyboardButton("➡️ အော်ဒါ အတည်ပြုမည်", callback_data="confirm_selection"))
    action_row.append(InlineKeyboardButton("❌ မလုပ်တော့ပါ", callback_data="cancel_order"))
    keyboard.append(action_row)

    reply_markup = InlineKeyboardMarkup(keyboard)

    if hasattr(query_or_update, "edit_message_text"):
        await query_or_update.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await query_or_update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def movie_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle movie selection toggle button callback."""
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()

    if not await rate_limit_check(update, "cb_toggle"):
        return

    user = update.effective_user
    data = query.data or ""
    movie_id = data.split(":")[1] if ":" in data else ""

    session = await session_service.get_session(user.id)
    if not session or session.state != SessionState.SELECTING_PACKAGE:
        await query.answer("အဆင်မပြေပါ။ ကျေးဇူးပြု၍ /start ဖြင့် ပြန်စပါ။", show_alert=True)
        return

    selected = list(session.selectedMovieIds)
    pkg_size = session.packageSize or 1

    if movie_id in selected:
        selected.remove(movie_id)
    else:
        if len(selected) >= pkg_size:
            await query.answer(f"လူကြီးမင်းသည် {pkg_size} ကားသာ ရွေးချယ်ခွင့် ရှိပါသည်။", show_alert=True)
            return
        selected.append(movie_id)

    # Update session in DB
    await session_service.set_state(
        telegram_id=user.id,
        state=SessionState.SELECTING_PACKAGE,
        package_size=pkg_size,
        selected_movie_ids=selected
    )

    await show_movie_selection_grid(query, user.id, pkg_size, selected)


async def confirm_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Confirm movie selection and display payment method options."""
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()

    if not await rate_limit_check(update, "cb_confirm"):
        return

    user = update.effective_user
    session = await session_service.get_session(user.id)

    if not session or session.state != SessionState.SELECTING_PACKAGE:
        await query.answer("အဆင်မပြေပါ။ ကျေးဇူးပြု၍ /start ဖြင့် ပြန်စပါ။", show_alert=True)
        return

    pkg_size = session.packageSize
    selected_ids = session.selectedMovieIds

    if len(selected_ids) != pkg_size:
        await query.answer(f"ကျေးဇူးပြု၍ ဇာတ်ကား {pkg_size} ကား တိတိကျကျ ရွေးချယ်ပေးပါရှင်။", show_alert=True)
        return

    # Create draft order in PENDING_PAYMENT state
    try:
        order = await order_service.create_order(
            telegram_id=user.id,
            package_size=pkg_size,
            movie_ids=selected_ids
        )
    except ValueError as e:
        await query.edit_message_text(f"❌ Order ဖန်တီးရာတွင် အမှားအယွင်းရှိပါသည်: {str(e)}")
        return

    # Update session to SELECTING_PAYMENT with activeOrderId
    await session_service.set_state(
        telegram_id=user.id,
        state=SessionState.SELECTING_PAYMENT,
        package_size=pkg_size,
        selected_movie_ids=selected_ids,
        active_order_id=str(order.id)
    )

    # Prompt for payment method selection
    keyboard = [
        [
            InlineKeyboardButton("📱 KBZPay", callback_data="pay:kpay"),
            InlineKeyboardButton("🌊 WavePay", callback_data="pay:wave"),
        ],
        [
            InlineKeyboardButton("💳 AYA Pay", callback_data="pay:aya"),
            InlineKeyboardButton("🏦 UAB Pay", callback_data="pay:uab"),
        ],
        [
            InlineKeyboardButton("❌ အော်ဒါ ဖျက်မည်", callback_data="cancel_order")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    summary_text = (
        f"📝 **အော်ဒါ အချက်အလက်များ**\n\n"
        f"• Order Code: **#{order.orderCode}**\n"
        f"• ဇာတ်ကား အရေအတွက်: **{order.packageSize} ကား**\n"
        f"• ကျသင့်ငွေ: **{order.totalPrice:,} MMK**\n\n"
        f"ကျေးဇူးပြု၍ ငွေပေးချေလိုသော **Payment Method** ကို ရွေးချယ်ပါ။"
    )

    await query.edit_message_text(summary_text, reply_markup=reply_markup, parse_mode="Markdown")


async def payment_method_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle payment method selection (pay:kpay, pay:wave, pay:aya, pay:uab)."""
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()

    if not await rate_limit_check(update, "cb_pay"):
        return

    user = update.effective_user
    data = query.data or ""
    pay_method = data.split(":")[1].lower() if ":" in data else ""

    session = await session_service.get_session(user.id)
    if not session or not session.activeOrderId or session.state != SessionState.SELECTING_PAYMENT:
        await query.answer("အဆင်မပြေပါ။ ကျေးဇူးပြု၍ /start ဖြင့် ပြန်စပါ။", show_alert=True)
        return

    # Update order with payment method
    order = await order_service.get_order_by_id(session.activeOrderId)
    if not order:
        await query.edit_message_text("❌ Order ရှာမတွေ့ပါ။ ကျေးဇူးပြု၍ ပြန်လည် စတင်ပါ။")
        return

    # Set order payment method & session state
    await order_service.update_payment_method(order.id, pay_method)

    await session_service.set_state(
        telegram_id=user.id,
        state=SessionState.AWAITING_SCREENSHOT,
        package_size=session.packageSize,
        selected_movie_ids=session.selectedMovieIds,
        active_order_id=session.activeOrderId
    )

    # Get payment account info
    pay_info = config.payment_methods.get(pay_method, {})
    account_name = pay_info.get("account_name", "")
    phone = pay_info.get("phone", "")
    
    pay_instructions = messages.payment_instructions(
        method_name=pay_info.get("name", pay_method.upper()),
        account_name=account_name,
        phone=phone,
        amount=order.totalPrice,
        order_code=order.orderCode
    )

    keyboard = [[InlineKeyboardButton("❌ အော်ဒါ မလုပ်တော့ပါ", callback_data="cancel_order")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(pay_instructions, reply_markup=reply_markup, parse_mode="Markdown")


async def photo_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages for payment screenshot submission."""
    if not update.effective_user or not update.message or not update.message.photo:
        return

    user = update.effective_user
    if not await rate_limit_check(update, "msg_photo"):
        return

    session = await session_service.get_session(user.id)
    if not session or not session.activeOrderId or session.state != SessionState.AWAITING_SCREENSHOT:
        await update.message.reply_text("ℹ️ လတ်တလော ငွေလွှဲပြေစာ ပေးပို့ရန် Order မရှိပါ။ ဇာတ်ကားဝယ်ယူရန် /start ကို နှိပ်ပါ။")
        return

    # Get largest photo size file_id
    photo = update.message.photo[-1]
    file_id = photo.file_id

    # Submit screenshot to order service
    success, err_msg = await order_service.submit_screenshot(
        order_id=session.activeOrderId,
        telegram_id=user.id,
        file_id=file_id
    )

    if not success:
        await update.message.reply_text(f"❌ {err_msg}")
        return

    # Get order and movie info to notify admins
    active_order_id = session.activeOrderId
    await session_service.clear_session(user.id)

    order = await order_service.get_order_by_id(active_order_id)
    if order:
        movies = await movie_service.get_movies_by_ids(order.movieIds)
        user_info = {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
        from app.services.notifier import notifier_service
        # Trigger background admin notification
        import asyncio
        asyncio.create_task(notifier_service.notify_admins_new_order(
            order=order,
            screenshot_file_id=file_id,
            user_info=user_info,
            selected_movies=movies
        ))

    # Confirmation text
    confirm_text = (
        f"✅ **ငွေလွှဲပြေစာ လက်ခံရရှိပါသည်!**\n\n"
        f"လူကြီးမင်း၏ ငွေလွှဲပြေစာကို Admin အဖွဲ့မှ စစ်ဆေးနေပါသည်။\n"
        f"စစ်ဆေးပြီးပါက ဇာတ်ကား ကြည့်ရှုရန် Link ကို ဤနေရာတွင် မကြာမီ ပေးပို့ပေးသွားပါမည်။\n\n"
        f"• Order အခြေအနေကို /orders ဖြင့် စစ်ဆေးနိုင်ပါသည်။"
    )

    await update.message.reply_text(confirm_text, parse_mode="Markdown")


async def cancel_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline cancel button callback."""
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()

    user = update.effective_user
    session = await session_service.get_session(user.id)

    if session and session.activeOrderId:
        await order_service.cancel_order(
            order_id=session.activeOrderId,
            telegram_id=user.id,
            reason="Cancelled via inline button"
        )

    await session_service.clear_session(user.id)
    if hasattr(query, "edit_message_text"):
        await query.edit_message_text(messages.ORDER_CANCELLED)


async def order_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle order detail view callback."""
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()

    data = query.data or ""
    order_code = data.split(":")[1] if ":" in data else ""
    order = await order_service.get_order_by_code(order_code)

    if not order or order.telegramUserId != update.effective_user.id:
        await query.answer("Order ရှာမတွေ့ပါ သို့မဟုတ် ကြည့်ရှုခွင့် မရှိပါ။", show_alert=True)
        return

    status_str = messages.STATUS_LABELS.get(order.status.value, order.status.value)
    
    text = (
        f"📋 **Order #{order.orderCode} အသေးစိတ်**\n\n"
        f"• အခြေအနေ: **{status_str}**\n"
        f"• ပက်ကေ့ဂျ်: **{order.packageSize} ကား**\n"
        f"• ကျသင့်ငွေ: **{order.totalPrice:,} MMK**\n"
        f"• ဝယ်ယူသည့်နေ့: **{order.createdAt.strftime('%Y-%m-%d %H:%M')}**\n"
    )

    if order.status.value == "APPROVED":
        # Get movie links
        movies = await movie_service.get_movies_by_ids(order.movieIds, include_watch_link=True)
        text += "\n🎬 **ကြည့်ရှုနိုင်သော Link များ:**\n"
        for idx, m in enumerate(movies, 1):
            title = m.titleMM or m.titleEn
            link = m.watchLink or "Link ဖြည့်သွင်းထားခြင်း မရှိပါ"
            text += f"{idx}. {title}\n👉 [ကြည့်ရန် နှိပ်ပါ]({link})\n\n"

    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)
