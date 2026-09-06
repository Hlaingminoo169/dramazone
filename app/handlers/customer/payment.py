"""
app/handlers/customer/payment.py

Payment method selection + screenshot submission — Steps 10 & 11.
"""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters, Application

from app.config import settings
from app.services.session_service import get_session, set_session, clear_session
from app.services.order_service import create_order, attach_screenshot
from app.services.user_service import get_user
from app.types import BotType, PaymentMethod, SessionState

logger = logging.getLogger(__name__)

CB_PAY_SELECT = "pay_select"
CB_KPAY = "pay_kpay"
CB_WAVE = "pay_wave"


def _payment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 KPay", callback_data=CB_KPAY)],
        [InlineKeyboardButton("🌊 Wave", callback_data=CB_WAVE)],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_order")],
    ])


async def show_payment_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show KPay / Wave selection."""
    query = update.callback_query
    await query.answer()

    tg_user = update.effective_user
    session = get_session(tg_user.id, BotType.CUSTOMER)
    if not session or session.get("state") != SessionState.SELECTING_PAYMENT:
        await query.edit_message_text("⚠️ Session သက်တမ်းကုန်သွားပါပြီ။ /start ကိုနှိပ်ပါ။")
        return

    await query.edit_message_text(
        "💳 *Payment Method ရွေးပါ*",
        parse_mode="Markdown",
        reply_markup=_payment_keyboard(),
    )


async def _send_payment_instructions(
    update: Update,
    method: str,
) -> None:
    """Send payment account details (and optional QR)."""
    query = update.callback_query

    if method == PaymentMethod.KPAY:
        phone = settings.kpay_phone or "09777720344"
        name = settings.kpay_account_name or "Myat Nyein Ngon"
        qr_file_id = settings.qr_kpay_file_id
        method_label = "KPay"
    else:
        phone = settings.wave_phone or "09777720344"
        name = settings.wave_account_name or "Myat Nyein Ngon"
        qr_file_id = settings.qr_wave_file_id
        method_label = "Wave"

    text = (
        f"📱 *{method_label} ဖြင့် ငွေလွှဲပေးပို့ပါ*\n\n"
        f"Phone: `{phone}`\n"
        f"Account Name: *{name}*\n\n"
        f"ငွေလွှဲပြီးနောက် Screenshot ပေးပို့ပေးပါ။\n\n"
        f"⚠️ ကျေးဇူးပြု၍ ငွေလွှဲပြီးသော Screenshot ကို ပေးပို့ပါ။"
    )

    if qr_file_id:
        await query.message.reply_photo(
            photo=qr_file_id,
            caption=text,
            parse_mode="Markdown",
        )
    else:
        await query.edit_message_text(text, parse_mode="Markdown")


async def handle_kpay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_payment_choice(update, context, PaymentMethod.KPAY)


async def handle_wave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_payment_choice(update, context, PaymentMethod.WAVE)


async def _handle_payment_choice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    method: str,
) -> None:
    """Store payment method in session and send instructions."""
    query = update.callback_query
    await query.answer()
    tg_user = update.effective_user

    session = get_session(tg_user.id, BotType.CUSTOMER)
    if not session or session.get("state") != SessionState.SELECTING_PAYMENT:
        await query.edit_message_text("⚠️ Session သက်တမ်းကုန်သွားပါပြီ။ /start ကိုနှိပ်ပါ။")
        return

    data = session.get("data", {})
    quantity: int = data.get("quantity", 1)
    amount: int = data.get("amount", 0)
    movie_snapshots: list = data.get("movieSnapshots", [])

    # Create the order in PENDING_PAYMENT status.
    try:
        order = create_order(
            telegram_user_id=tg_user.id,
            quantity=quantity,
            amount=amount,
            payment_method=method,
            selected_movies=movie_snapshots,
        )
    except Exception as exc:
        logger.exception("Failed to create order for user %s: %s", tg_user.id, exc)
        await query.edit_message_text(
            "⚠️ Order ပြုလုပ်ရာတွင် အမှားတစ်ခုဖြစ်ပေါ်နေပါသည်။ ခဏကြာပြီးနောက် ပြန်ကြိုးစားပါ။"
        )
        return

    order_id = str(order["_id"])
    order_code = order["orderCode"]

    # Transition session to WAITING_SCREENSHOT.
    set_session(
        tg_user.id,
        BotType.CUSTOMER,
        SessionState.WAITING_SCREENSHOT,
        data={"orderId": order_id, "paymentMethod": method},
    )

    logger.info("Order %s created for user %s via %s", order_code, tg_user.id, method)

    await _send_payment_instructions(update, method)


async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Receive payment screenshot.

    Accepts photos and image documents.
    Attaches the file ID to the order and notifies admins.
    """
    tg_user = update.effective_user
    session = get_session(tg_user.id, BotType.CUSTOMER)

    if not session or session.get("state") != SessionState.WAITING_SCREENSHOT:
        # Ignore photos when not in screenshot state.
        return

    # Extract the best file ID from the message.
    file_id: str | None = None
    if update.message.photo:
        # Telegram photos come in multiple sizes; use the largest.
        file_id = update.message.photo[-1].file_id
    elif update.message.document and update.message.document.mime_type.startswith("image/"):
        file_id = update.message.document.file_id

    if not file_id:
        await update.message.reply_text(
            "⚠️ ကျေးဇူးပြု၍ Screenshot ဓာတ်ပုံကိုသာ ပေးပို့ပါ။"
        )
        return

    session_data = session.get("data", {})
    order_id = session_data.get("orderId")
    payment_method = session_data.get("paymentMethod", "")

    if not order_id:
        await update.message.reply_text(
            "⚠️ Order မတွေ့ပါ။ /start ကိုနှိပ်ပြီး ပြန်စပါ။"
        )
        return

    # Attach screenshot → WAITING_APPROVAL.
    updated_order = attach_screenshot(order_id, file_id)
    if not updated_order:
        await update.message.reply_text(
            "⚠️ Order ကို update လုပ်ရာတွင် အမှားဖြစ်ပေါ်နေပါသည်။ /start ကိုနှိပ်ပြီး ပြန်စပါ။"
        )
        return

    # Clear session — flow is complete from customer side.
    clear_session(tg_user.id, BotType.CUSTOMER)

    await update.message.reply_text(
        "⏳ *Payment စစ်ဆေးနေပါသည်။*\n\n"
        f"Order ID: `{updated_order['orderCode']}`\n\n"
        "Admin မှ စစ်ဆေးပြီးနောက် အတည်ပြုပေးပါမည်။\n"
        "ကျေးဇူးပြု၍ ခနစောင့်ပါ။",
        parse_mode="Markdown",
    )

    # Notify admins asynchronously.
    try:
        from app.bots.customer_bot import get_customer_app
        from app.bots.admin_bot import get_admin_app
        from app.services.notification_service import notify_admins_new_payment
        from app.services.user_service import get_user

        user = get_user(tg_user.id) or {"firstName": tg_user.first_name, "username": tg_user.username}

        await notify_admins_new_payment(
            order=updated_order,
            user=user,
            screenshot_file_id=file_id,
            customer_bot=get_customer_app().bot,
            admin_bot=get_admin_app().bot,
        )
    except Exception as exc:
        logger.exception("Failed to notify admins for order %s: %s", order_id, exc)


def register(app: Application) -> None:
    """Register payment handlers."""
    app.add_handler(CallbackQueryHandler(show_payment_selection, pattern=f"^{CB_PAY_SELECT}$"))
    app.add_handler(CallbackQueryHandler(handle_kpay, pattern=f"^{CB_KPAY}$"))
    app.add_handler(CallbackQueryHandler(handle_wave, pattern=f"^{CB_WAVE}$"))
    # Screenshot handler: photos and image documents.
    app.add_handler(
        MessageHandler(
            filters.PHOTO | (filters.Document.IMAGE),
            handle_screenshot,
        )
    )
