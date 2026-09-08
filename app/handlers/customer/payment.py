"""
app/handlers/customer/payment.py

Payment method selection + screenshot submission.

Supports: KPay, Wave, AYAPay, UABPay
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
from app.utils.anti_flood import check_flood

logger = logging.getLogger(__name__)

# ── Callback data constants ────────────────────────────────────────────────────
CB_PAY_SELECT = "pay_select"
CB_KPAY = "pay_kpay"
CB_WAVE = "pay_wave"
CB_AYAPAY = "pay_ayapay"
CB_UABPAY = "pay_uabpay"


def _payment_keyboard() -> InlineKeyboardMarkup:
    """4-option payment keyboard arranged in a 2x2 grid + cancel."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 KPay",   callback_data=CB_KPAY),
            InlineKeyboardButton("🌊 Wave",   callback_data=CB_WAVE),
        ],
        [
            InlineKeyboardButton("💳 AYAPay", callback_data=CB_AYAPAY),
            InlineKeyboardButton("🏦 UABPay", callback_data=CB_UABPAY),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_order")],
    ])


# ── Payment config lookup ──────────────────────────────────────────────────────
_PAYMENT_CONFIG: dict[str, dict] = {
    PaymentMethod.KPAY: {
        "label":  "KPay",
        "emoji":  "📱",
        "phone":  lambda: settings.kpay_phone or "09777720344",
        "name":   lambda: settings.kpay_account_name or "Myat Nyein Ngon",
        "qr":     lambda: settings.qr_kpay_file_id,
    },
    PaymentMethod.WAVE: {
        "label":  "Wave",
        "emoji":  "🌊",
        "phone":  lambda: settings.wave_phone or "09777720344",
        "name":   lambda: settings.wave_account_name or "Myat Nyein Ngon",
        "qr":     lambda: settings.qr_wave_file_id,
    },
    PaymentMethod.AYAPAY: {
        "label":  "AYAPay",
        "emoji":  "💳",
        "phone":  lambda: settings.ayapay_phone or "09768908422",
        "name":   lambda: settings.ayapay_account_name or "Hlaing Min Oo",
        "qr":     lambda: settings.qr_ayapay_file_id,
    },
    PaymentMethod.UABPAY: {
        "label":  "UABPay",
        "emoji":  "🏦",
        "phone":  lambda: settings.uabpay_phone or "09768908422",
        "name":   lambda: settings.uabpay_account_name or "Hlaing Min Oo",
        "qr":     lambda: settings.qr_uabpay_file_id,
    },
}


# ── Handlers ───────────────────────────────────────────────────────────────────

async def show_payment_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the payment method selection keyboard."""
    query = update.callback_query
    await query.answer()

    if await check_flood(update, context):
        return

    tg_user = update.effective_user
    session = get_session(tg_user.id, BotType.CUSTOMER)
    if not session or session.get("state") != SessionState.SELECTING_PAYMENT:
        await query.edit_message_text("⚠️ Session သက်တမ်းကုန်သွားပါပြီ။ /start ကိုနှိပ်ပါ။")
        return

    await query.edit_message_text(
        "💳 *Payment Method ရွေးပါ*\n\n"
        "KPay / Wave / AYAPay / UABPay တစ်ခုကို ရွေးချယ်ပေးပါ။",
        parse_mode="Markdown",
        reply_markup=_payment_keyboard(),
    )


async def _send_payment_instructions(update: Update, method: str) -> None:
    """Send payment account details (and optional QR code) for the chosen method."""
    query = update.callback_query
    cfg = _PAYMENT_CONFIG.get(method)
    if not cfg:
        await query.edit_message_text("⚠️ Payment method မသိပါ။ /start ကိုနှိပ်ပါ။")
        return

    phone      = cfg["phone"]()
    name       = cfg["name"]()
    qr_file_id = cfg["qr"]()
    emoji      = cfg["emoji"]
    label      = cfg["label"]

    text = (
        f"{emoji} *{label} ဖြင့် ငွေလွှဲပေးပို့ပါ*\n\n"
        f"📞 Phone: `{phone}`\n"
        f"👤 Account Name: *{name}*\n\n"
        f"⚠️ *အရေးကြီး:* ငွေလွှဲသည့်အခါ Note/Remark တွင် "
        f"မိမိ၏ *Telegram Name* (သို့မဟုတ်) Username ကို ထည့်သွင်းပေးပါရန်။\n\n"
        f"ငွေလွှဲပြီးပါက ငွေလွှဲပြေစာ Screenshot ကို ပေးပို့ပေးပါ။"
    )

    if qr_file_id:
        await query.message.reply_photo(
            photo=qr_file_id,
            caption=text,
            parse_mode="Markdown",
        )
    else:
        await query.edit_message_text(text, parse_mode="Markdown")


async def _handle_payment_choice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    method: str,
) -> None:
    """
    Common handler for any payment method selection.

    1. Validates the session is still in SELECTING_PAYMENT state.
    2. Creates the order in PENDING_PAYMENT status.
    3. Transitions session to WAITING_SCREENSHOT.
    4. Sends payment instructions to the customer.
    """
    query = update.callback_query
    await query.answer()
    tg_user = update.effective_user

    # Flood protection — prevents rapid payment method switching
    if await check_flood(update, context):
        return

    session = get_session(tg_user.id, BotType.CUSTOMER)
    if not session or session.get("state") != SessionState.SELECTING_PAYMENT:
        await query.edit_message_text("⚠️ Session သက်တမ်းကုန်သွားပါပြီ။ /start ကိုနှိပ်ပါ။")
        return

    data            = session.get("data", {})
    quantity: int   = data.get("quantity", 1)
    amount: int     = data.get("amount", 0)
    movie_snapshots = data.get("movieSnapshots", [])

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

    order_id   = str(order["_id"])
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


# ── Per-method handler shims ──────────────────────────────────────────────────

async def handle_kpay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_payment_choice(update, context, PaymentMethod.KPAY)


async def handle_wave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_payment_choice(update, context, PaymentMethod.WAVE)


async def handle_ayapay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_payment_choice(update, context, PaymentMethod.AYAPAY)


async def handle_uabpay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_payment_choice(update, context, PaymentMethod.UABPAY)


# ── Screenshot handler ────────────────────────────────────────────────────────

async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Receive payment screenshot from the customer.

    Accepts both compressed photos and image documents (to preserve quality).
    Attaches the Telegram file_id to the order and notifies all admins.
    """
    tg_user = update.effective_user
    session = get_session(tg_user.id, BotType.CUSTOMER)

    if not session or session.get("state") != SessionState.WAITING_SCREENSHOT:
        # Silently ignore photos when not awaiting a screenshot.
        return

    # Extract the best-quality file ID from the message.
    file_id: str | None = None
    if update.message.photo:
        # Telegram sends multiple sizes; pick the largest.
        file_id = update.message.photo[-1].file_id
    elif update.message.document and update.message.document.mime_type.startswith("image/"):
        file_id = update.message.document.file_id

    if not file_id:
        await update.message.reply_text(
            "⚠️ ကျေးဇူးပြု၍ Screenshot ဓာတ်ပုံကိုသာ ပေးပို့ပါ။"
        )
        return

    session_data   = session.get("data", {})
    order_id       = session_data.get("orderId")
    payment_method = session_data.get("paymentMethod", "")

    if not order_id:
        await update.message.reply_text(
            "⚠️ Order မတွေ့ပါ။ /start ကိုနှိပ်ပြီး ပြန်စပါ။"
        )
        return

    # Attach screenshot and move order → WAITING_APPROVAL.
    updated_order = attach_screenshot(order_id, file_id)
    if not updated_order:
        await update.message.reply_text(
            "⚠️ Order ကို update လုပ်ရာတွင် အမှားဖြစ်ပေါ်နေပါသည်။ /start ကိုနှိပ်ပြီး ပြန်စပါ။"
        )
        return

    # Flow complete from customer side — clear session.
    clear_session(tg_user.id, BotType.CUSTOMER)

    # Determine which payment label to show in confirmation
    cfg = _PAYMENT_CONFIG.get(payment_method, {})
    method_label = cfg.get("label", payment_method) if cfg else payment_method

    await update.message.reply_text(
        "⏳ *Payment စစ်ဆေးနေပါသည်။*\n\n"
        f"Order ID: `{updated_order['orderCode']}`\n"
        f"Payment Method: {method_label}\n\n"
        "Admin မှ စစ်ဆေးပြီးနောက် အတည်ပြုပေးပါမည်။\n"
        "ကျေးဇူးပြု၍ ခနစောင့်ပါ။",
        parse_mode="Markdown",
    )

    # Notify all admins asynchronously.
    try:
        from app.bots.customer_bot import get_customer_app
        from app.bots.admin_bot import get_admin_app
        from app.services.notification_service import notify_admins_new_payment
        from app.services.user_service import upsert_user

        user = upsert_user(tg_user)

        await notify_admins_new_payment(
            order=updated_order,
            user=user,
            screenshot_file_id=file_id,
            customer_bot=get_customer_app().bot,
            admin_bot=get_admin_app().bot,
        )
    except Exception as exc:
        logger.exception("Failed to notify admins for order %s: %s", order_id, exc)


# ── Registration ───────────────────────────────────────────────────────────────

def register(app: Application) -> None:
    """Register all payment-related handlers."""
    app.add_handler(CallbackQueryHandler(show_payment_selection, pattern=f"^{CB_PAY_SELECT}$"))
    app.add_handler(CallbackQueryHandler(handle_kpay,    pattern=f"^{CB_KPAY}$"))
    app.add_handler(CallbackQueryHandler(handle_wave,    pattern=f"^{CB_WAVE}$"))
    app.add_handler(CallbackQueryHandler(handle_ayapay,  pattern=f"^{CB_AYAPAY}$"))
    app.add_handler(CallbackQueryHandler(handle_uabpay,  pattern=f"^{CB_UABPAY}$"))
    # Screenshot handler: accept both compressed photos and image documents.
    app.add_handler(
        MessageHandler(
            filters.PHOTO | filters.Document.IMAGE,
            handle_screenshot,
        )
    )
