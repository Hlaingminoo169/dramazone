"""
app/types.py

Shared constants and type definitions used throughout the project.

Using string literals (not Enum) keeps MongoDB documents human-readable.
"""
from __future__ import annotations


# ── Order statuses ────────────────────────────────────────────────────────────
class OrderStatus:
    PENDING_PAYMENT = "PENDING_PAYMENT"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

    ALL = (PENDING_PAYMENT, WAITING_APPROVAL, APPROVED, REJECTED, CANCELLED)


# ── Session states ─────────────────────────────────────────────────────────────
class SessionState:
    SELECTING_PACKAGE = "SELECTING_PACKAGE"
    SELECTING_MOVIES = "SELECTING_MOVIES"
    CONFIRMING_ORDER = "CONFIRMING_ORDER"
    SELECTING_PAYMENT = "SELECTING_PAYMENT"
    WAITING_SCREENSHOT = "WAITING_SCREENSHOT"
    WAITING_FOR_REJECTION_REASON = "WAITING_FOR_REJECTION_REASON"


# ── Bot types (used in sessions) ──────────────────────────────────────────────
class BotType:
    CUSTOMER = "customer"
    ADMIN = "admin"


# ── Payment methods ───────────────────────────────────────────────────────────
class PaymentMethod:
    KPAY = "KPay"
    WAVE = "Wave"
    AYAPAY = "AYAPay"
    UABPAY = "UABPay"

    ALL = (KPAY, WAVE, AYAPAY, UABPAY)


# ── Collection names ──────────────────────────────────────────────────────────
class Collection:
    USERS = "users"
    MOVIES = "movies"
    ORDERS = "orders"
    SESSIONS = "sessions"
    SETTINGS = "settings"
