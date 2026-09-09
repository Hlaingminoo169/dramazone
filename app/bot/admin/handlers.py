"""
app/bot/admin/handlers.py
────────────────────────────────────────────────────────────────────────
Admin Telegram Bot Command & Callback Query Handlers.

Handles:
- /start, /admin: Admin dashboard & analytics summary
- /pending: Pending orders list & review actions
- /movies: Active movies list
- Callback Queries:
  - admin_approve:<order_code> -> Approve order & send watch links to customer
  - admin_reject:<order_code> -> Show rejection reason options
  - admin_reject_reason:<order_code>:<reason_key> -> Reject order with specific reason
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.services.admin_service import admin_service
from app.services.movie_service import movie_service
from app.services.order_service import order_service
from app.bot.admin import messages

logger = logging.getLogger("dramazone.bot.admin")


def admin_only(func):
    """Decorator to enforce Admin authorization check on handlers."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or not admin_service.is_admin(user.id):
            if update.callback_query:
                await update.callback_query.answer(messages.ACCESS_DENIED, show_alert=True)
            elif update.message:
                await update.message.reply_text(messages.ACCESS_DENIED, parse_mode="Markdown")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


@admin_only
async def admin_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start or /admin command for Admin Bot."""
    if not update.message:
        return

    stats = await admin_service.get_dashboard_stats()
    text = f"{messages.ADMIN_WELCOME}\n\n{messages.format_dashboard(stats)}"

    keyboard = [
        [InlineKeyboardButton("⏳ Pending Order များ စစ်ဆေးမည်", callback_data="admin_view_pending")],
        [InlineKeyboardButton("🔄 Dashboard Update ပြုလုပ်မည်", callback_data="admin_refresh_dashboard")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


@admin_only
async def pending_orders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /pending command - list all pending orders."""
    if not update.message:
        return

    orders = await admin_service.get_pending_orders(limit=10)
    if not orders:
        await update.message.reply_text(messages.NO_PENDING_ORDERS, parse_mode="Markdown")
        return

    await update.message.reply_text(f"⏳ **စစ်ဆေးရန် ကျန်ရှိနေသော Pending Order ({len(orders)}) ခု:**\n", parse_mode="Markdown")

    for order in orders:
        movies = await movie_service.get_movies_by_ids(order.movieIds)
        movie_titles = "\n".join([f"• {m.title or m.titleEn}" for m in movies])

        caption = (
            f"📦 **Order Code: #{order.orderCode}**\n"
            f"• Telegram ID: `{order.telegramId}`\n"
            f"• ဇာတ်ကား အရေအတွက်: **{order.packageSize} ကား**\n"
            f"• ကျသင့်ငွေ: **{order.totalAmount:,} MMK** ({order.paymentMethod.upper() if order.paymentMethod else 'N/A'})\n\n"
            f"🎬 **ရွေးချယ်ထားသော ဇာတ်ကားများ:**\n{movie_titles}\n"
        )

        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve:{order.orderCode}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject:{order.orderCode}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if order.paymentScreenshotFileId:
            await update.message.reply_photo(
                photo=order.paymentScreenshotFileId,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(caption, reply_markup=reply_markup, parse_mode="Markdown")


@admin_only
async def movies_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /movies command - list active catalog movies."""
    if not update.message:
        return

    movies = await movie_service.get_active_movies()
    if not movies:
        await update.message.reply_text("❌ စနစ်ထဲတွင် Active ဖြစ်နေသော ဇာတ်ကားများ မရှိသေးပါ။")
        return

    text = "🎬 **လက်ရှိ Active ဖြစ်နေသော ဇာတ်ကားများ List**\n\n"
    for idx, m in enumerate(movies, 1):
        text += f"{idx}. **{m.title or m.titleEn}**\n   Link: `{m.watchLink or 'N/A'}`\n\n"

    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


@admin_only
async def admin_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin_approve:<order_code> callback."""
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()

    user = update.effective_user
    order_code = query.data.split(":")[1]

    success, message, order = await admin_service.approve_order(
        order_code=order_code,
        admin_id=user.id,
        admin_username=user.username or ""
    )

    if not success:
        await query.answer(message, show_alert=True)
        return

    # Update admin message text / caption to reflect approval status
    admin_name = f"@{user.username}" if user.username else f"ID: {user.id}"
    updated_caption = (
        f"✅ **Order #{order_code} အား အတည်ပြုပြီးပါပြီ (APPROVED)**\n\n"
        f"• စစ်ဆေးခဲ့သူ Admin: **{admin_name}**\n"
        f"• Customer Telegram ID: `{order.telegramUserId}`\n"
        f"• ပက်ကေ့ဂျ်: **{order.packageSize} ကား** ({order.totalAmount:,} MMK)\n"
        f"• Watch Links များကို Customer ထံသို့ ပေးပို့ပြီးပါပြီ။"
    )

    if getattr(query.message, 'photo', None):
        await query.edit_message_caption(updated_caption, parse_mode="Markdown", reply_markup=None)
    elif hasattr(query, "edit_message_text"):
        await query.edit_message_text(updated_caption, parse_mode="Markdown", reply_markup=None)


@admin_only
async def admin_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin_reject:<order_code> callback - show rejection reason prompt buttons."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    order_code = query.data.split(":")[1]

    # Present preset rejection reasons
    keyboard = []
    for reason_key, reason_label in messages.REJECT_REASON_OPTIONS.items():
        keyboard.append([
            InlineKeyboardButton(reason_label, callback_data=f"admin_reject_reason:{order_code}:{reason_key}")
        ])

    keyboard.append([InlineKeyboardButton("🔙 မလုပ်တော့ပါ (Back)", callback_data=f"admin_cancel_action:{order_code}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"❓ Order **#{order_code}** အား Reject လုပ်လိုသည့် အကြောင်းအရင်းကို ရွေးချယ်ပေးပါ:"

    if query.message.photo:
        await query.edit_message_caption(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")


@admin_only
async def admin_reject_reason_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin_reject_reason:<order_code>:<reason_key> callback."""
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()

    user = update.effective_user
    parts = query.data.split(":")
    order_code = parts[1]
    reason_key = parts[2]

    reason_str = messages.REJECT_REASON_OPTIONS.get(reason_key, "ငွေလွှဲပြေစာ မမှန်ကန်ပါ")

    success, message, order = await admin_service.reject_order(
        order_code=order_code,
        admin_id=user.id,
        admin_username=user.username or "",
        reason=reason_str
    )

    if not success:
        await query.answer(message, show_alert=True)
        return

    admin_name = f"@{user.username}" if user.username else f"ID: {user.id}"
    updated_caption = (
        f"❌ **Order #{order_code} အား ငြင်းပယ်ပြီးပါပြီ (REJECTED)**\n\n"
        f"• ငြင်းပယ်ခဲ့သူ Admin: **{admin_name}**\n"
        f"• အကြောင်းအရင်း: **{reason_str}**\n"
        f"• Customer Telegram ID: `{order.telegramUserId}`\n"
        f"• Rejection notification အား Customer ထံ ပေးပို့ပြီးပါပြီ။"
    )

    if query.message and getattr(query.message, 'photo', None):
        await query.edit_message_caption(updated_caption, parse_mode="Markdown", reply_markup=None)
    else:
        if hasattr(query, "edit_message_text"):
            await query.edit_message_text(updated_caption, parse_mode="Markdown", reply_markup=None)


@admin_only
async def admin_dashboard_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Refresh dashboard callback."""
    query = update.callback_query
    if not query:
        return
    await query.answer("Dashboard updated!")

    stats = await admin_service.get_dashboard_stats()
    text = f"{messages.ADMIN_WELCOME}\n\n{messages.format_dashboard(stats)}"

    keyboard = [
        [InlineKeyboardButton("⏳ Pending Order များ စစ်ဆေးမည်", callback_data="admin_view_pending")],
        [InlineKeyboardButton("🔄 Dashboard Update ပြုလုပ်မည်", callback_data="admin_refresh_dashboard")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
