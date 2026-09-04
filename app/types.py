"""
DramaZone VIP Bot System
========================
Type definitions and enums shared across the entire application.
"""

from enum import Enum


class OrderStatus(str, Enum):
    """Fixed order status values — never use raw strings in application code."""
    PENDING_PAYMENT = "PENDING_PAYMENT"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class PaymentMethod(str, Enum):
    """Supported payment methods."""
    KPAY = "KPAY"
    WAVE = "WAVE"


class BotType(str, Enum):
    """Which bot a session belongs to."""
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"


class CustomerState(str, Enum):
    """Customer conversation states stored in MongoDB sessions."""
    IDLE = "IDLE"
    SELECTING_PACKAGE = "SELECTING_PACKAGE"
    ENTERING_CUSTOM_QUANTITY = "ENTERING_CUSTOM_QUANTITY"
    SELECTING_MOVIES = "SELECTING_MOVIES"
    CONFIRMING_ORDER = "CONFIRMING_ORDER"
    SELECTING_PAYMENT_METHOD = "SELECTING_PAYMENT_METHOD"
    WAITING_SCREENSHOT = "WAITING_SCREENSHOT"


class AdminState(str, Enum):
    """Admin conversation states stored in MongoDB sessions."""
    IDLE = "IDLE"
    WAITING_FOR_REJECTION_REASON = "WAITING_FOR_REJECTION_REASON"
