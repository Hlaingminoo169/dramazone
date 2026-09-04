"""
app/services/payment_service.py
================================
Payment method configuration loaded from MongoDB settings.
Centralizes all payment-related data — never duplicated in handlers.
"""

from __future__ import annotations

import logging

from pymongo.database import Database

from app.config import get_settings
from app.types import PaymentMethod

logger = logging.getLogger(__name__)


def get_payment_info(db: Database, method: PaymentMethod) -> dict:
    """
    Return payment details for the given method.
    Falls back to environment variables if the DB setting is missing.
    QR file_id is optional — returns None if not configured.

    Returns:
        {
            "method":       "KPAY" | "WAVE",
            "label":        "KPay" | "Wave Pay",
            "phone":        str,
            "account_name": str,
            "qr_file_id":   str | None,
        }
    """
    settings = get_settings()

    # Try loading overrides from DB settings collection
    doc = db.settings.find_one({"key": f"payment_{method.value.lower()}"})

    if method == PaymentMethod.KPAY:
        phone = (doc or {}).get("phone") or settings.kpay_phone
        account_name = (doc or {}).get("account_name") or settings.kpay_account_name
        qr_file_id = (doc or {}).get("qr_file_id") or settings.qr_kpay_file_id or None
        label = "KPay"
    else:  # WAVE
        phone = (doc or {}).get("phone") or settings.wave_phone
        account_name = (doc or {}).get("account_name") or settings.wave_account_name
        qr_file_id = (doc or {}).get("qr_file_id") or settings.qr_wave_file_id or None
        label = "Wave Pay"

    return {
        "method": method.value,
        "label": label,
        "phone": phone,
        "account_name": account_name,
        "qr_file_id": qr_file_id,
    }


def format_payment_message(info: dict, amount: int) -> str:
    """
    Build the payment instruction message shown to the customer.
    QR code section is omitted when not configured.
    """
    lines = [
        f"💳 <b>{info['label']} ဖြင့် ငွေပေးချေမည်</b>",
        "",
        f"📱 ဖုန်းနံပါတ်: <code>{info['phone']}</code>",
        f"👤 အကောင့်အမည်: <b>{info['account_name']}</b>",
        f"💰 ပေးချေရမည့်ငွေ: <b>{amount:,} MMK</b>",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "⚠️ <b>အရေးကြီးသောသတိပေးချက်</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "• ငွေပမာဏ ကြည်လင်ပြတ်သားရမည်",
        "• ငွေလွှဲသောနေ့ရက်/အချိန် ပြသရမည်",
        "• Screenshot ဖတ်ရှုနိုင်ရမည်",
        "",
        "💳 ငွေလွှဲပြီးပါက <b>Payment Screenshot</b> ကို အောက်တွင် ပို့ပေးပါ။",
    ]
    return "\n".join(lines)
