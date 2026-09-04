"""
app/handlers/customer/payment.py
==================================
Payment method selection and screenshot upload handling.
"""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.database.mongodb import get_db
from app.services.movie_service import get_movies_by_ids, snapshot_movie
from app.services.notification_service import notify_admins_new_order
from app.services.order_service import (
    create_order,
    get_pending_payment_order,
    submit_payment_screenshot,
)
from app.services.payment_service import format_payment_message, get_payment_info
from app.services.session_service import clear_session, get_session, set_session
from app.services.user_service import get_user
from app.types import BotType, CustomerState, PaymentMethod

logger = logging.getLogger(__name__)


async def order_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create the order in DB and show payment method selection."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    db = get_db()

    session = get_session(db, user.id, BotType.CUSTOMER)
    if session.get("state") != CustomerState.CONFIRMING_ORDER.value:
        await query.edit_message_text("⚠️ Session ကုန်သွားပါပြီ။ /start နှိပ်ပါ။")
        return

    session_data = session.get("data", {})
    quantity: int = session_data.get("quantity", 0)
    price: int = session_data.get("price", 0)
    selected_ids: list[str] = session_data.get("selected_movie_ids", [])

    if not selected_ids or quantity == 0 or price == 0:
        await query.edit_message_text("⚠️ Session ကုန်သွားပါပြီ။ /start နှိပ်ပါ။")
        return

    # Fetch and snapshot movies
    movies = get_movies_by_ids(db, selected_ids)
    if len(movies) != quantity:
        await query.edit_message_text("❌ ရွေးချယ်ထားသောကားများ မတွေ့ပါ။ /start နှိပ်ပါ။")
        return

    snapshots = [snapshot_movie(m) for m in movies]

    # Create order record
    order = create_order(db, user.id, quantity, price, snapshots)
    order_code = order["orderCode"]

    # Update session with order code, move to payment method selection
    session_data["order_code"] = order_code
    set_session(db, user.id, BotType.CUSTOMER,
                state=CustomerState.SELECTING_PAYMENT_METHOD.value,
                data=session_data)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 KPay", callback_data=f"pay:KPAY:{order_code}")],
        [InlineKeyboardButton("💳 Wave Pay", callback_data=f"pay:WAVE:{order_code}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"pay:cancel:{order_code}")],
    ])

    await query.edit_message_text(
        f"✅ Order <b>{order_code}</b> ဖန်တီးပြီးပါပြီ။\n\n"
        f"💰 ကျသင့်ငွေ: <b>{price:,} MMK</b>\n\n"
        "ငွေပေးချေမည့်နည်းလမ်းကို ရွေးချယ်ပါ:",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def payment_method_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show payment details after method selection."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")  # "pay:KPAY:ORD-1234"
    if len(parts) != 3:
        await query.edit_message_text("❌ မမှန်ကန်သောရွေးချယ်မှု။")
        return

    _, method_str, order_code = parts

    if method_str == "cancel":
        user = update.effective_user
        db = get_db()
        from app.services.order_service import cancel_order
        cancel_order(db, order_code, user.id)
        clear_session(db, user.id, BotType.CUSTOMER)
        from app.handlers.customer.start import MAIN_MENU_TEXT, MAIN_MENU_KEYBOARD
        await query.edit_message_text(
            "❌ Order ပယ်ဖျက်လိုက်ပါပြီ။\n\n" + MAIN_MENU_TEXT,
            parse_mode="HTML",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return

    try:
        payment_method = PaymentMethod(method_str)
    except ValueError:
        await query.edit_message_text("❌ မမှန်ကန်သောငွေပေးချေမှုနည်းလမ်း။")
        return

    user = update.effective_user
    db = get_db()

    # Fetch order to get amount
    from app.services.order_service import get_order_by_code
    order = get_order_by_code(db, order_code)
    if not order or order["telegramUserId"] != user.id:
        await query.edit_message_text("❌ Order မတွေ့ပါ။")
        return

    amount = order["amount"]

    # Update session with chosen method, move to screenshot waiting
    session = get_session(db, user.id, BotType.CUSTOMER)
    session_data = session.get("data", {})
    session_data["payment_method"] = payment_method.value
    session_data["order_code"] = order_code
    set_session(db, user.id, BotType.CUSTOMER,
                state=CustomerState.WAITING_SCREENSHOT.value,
                data=session_data)

    # Get payment details
    info = get_payment_info(db, payment_method)
    msg = format_payment_message(info, amount)

    # Send QR if available
    qr_file_id = info.get("qr_file_id")
    if qr_file_id:
        try:
            await query.message.reply_photo(
                photo=qr_file_id,
                caption=msg,
                parse_mode="HTML",
            )
            await query.delete_message()
        except Exception:
            await query.edit_message_text(msg, parse_mode="HTML")
    else:
        await query.edit_message_text(msg, parse_mode="HTML")


async def screenshot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle customer uploading a payment screenshot (photo or image document).
    Validates session, stores file_id, notifies admins.
    """
    user = update.effective_user
    db = get_db()

    session = get_session(db, user.id, BotType.CUSTOMER)
    if session.get("state") != CustomerState.WAITING_SCREENSHOT.value:
        return  # Not waiting for screenshot — ignore silently

    session_data = session.get("data", {})
    order_code: str | None = session_data.get("order_code")
    payment_method_str: str | None = session_data.get("payment_method")

    if not order_code or not payment_method_str:
        await update.message.reply_text("⚠️ Session ကုန်သွားပါပြီ။ /start နှိပ်ပါ။")
        return

    # Extract file_id — support both photo and document (image)
    file_id: str | None = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id  # largest size
    elif update.message.document and update.message.document.mime_type and \
            update.message.document.mime_type.startswith("image/"):
        file_id = update.message.document.file_id

    if not file_id:
        await update.message.reply_text(
            "❌ ကျေးဇူးပြု၍ Payment Screenshot (ဓာတ်ပုံ) ပေးပို့ပါ။"
        )
        return

    try:
        payment_method = PaymentMethod(payment_method_str)
    except ValueError:
        await update.message.reply_text("⚠️ Session ကုန်သွားပါပြီ။ /start နှိပ်ပါ။")
        return

    # Update order in DB
    success = submit_payment_screenshot(db, order_code, user.id, file_id, payment_method)
    if not success:
        await update.message.reply_text(
            "❌ Order အချက်အလက် ရှာမတွေ့ပါ။ /start နှိပ်ပါ။"
        )
        return

    # Clear session
    clear_session(db, user.id, BotType.CUSTOMER)

    await update.message.reply_text(
        "⏳ <b>Payment စစ်ဆေးနေပါသည်။</b>\n\n"
        "Admin မှ စစ်ဆေးပြီးနောက် အတည်ပြုပေးပါမည်။\n"
        "ခဏစောင့်ပေးပါ — ကျေးဇူးတင်ပါသည်။",
        parse_mode="HTML",
    )

    # Notify admins (async — don't block customer response)
    order = get_order_by_code(db, order_code)  # noqa: re-fetch after update
    if not order:
        logger.error("Order %s not found after screenshot submission.", order_code)
        return

    customer_doc = get_user(db, user.id) or {
        "telegramId": user.id,
        "firstName": user.first_name or "",
        "lastName": user.last_name or "",
        "username": user.username or "",
    }

    from app.bots.customer_bot import get_customer_bot
    from app.bots.admin_bot import get_admin_bot

    customer_bot = get_customer_bot()
    admin_bot = get_admin_bot()

    await notify_admins_new_order(customer_bot, admin_bot, order, customer_doc)


def get_order_by_code(db, order_code):
    return db.orders.find_one({"orderCode": order_code})
