"""
app/utils/pricing.py
====================
Pricing logic — loaded from MongoDB settings collection.
Never hard-codes prices inside handlers.
"""

from __future__ import annotations

from pymongo.database import Database

from app.utils.numbers import format_mmk


def get_pricing_table(db: Database) -> list[dict]:
    """
    Return the pricing list from the settings collection.
    Each item: { quantity: int, price: int, label: str }
    """
    doc = db.settings.find_one({"key": "pricing"})
    if doc and "value" in doc:
        return doc["value"]
    return []


def get_price_for_quantity(db: Database, quantity: int) -> int | None:
    """
    Return the price (MMK) for a given quantity.
    Returns None if no exact match exists in the pricing table.
    """
    table = get_pricing_table(db)
    for item in table:
        if item["quantity"] == quantity:
            return item["price"]
    return None


def calculate_price(db: Database, quantity: int) -> int | None:
    """
    Calculate price for a quantity.
    Returns the configured price if an exact package exists,
    otherwise returns None (do NOT silently invent a price).
    """
    return get_price_for_quantity(db, quantity)


def format_price_for_quantity(db: Database, quantity: int) -> str:
    """
    Human-readable price string for a quantity, or an error message.
    """
    price = calculate_price(db, quantity)
    if price is None:
        return f"{quantity} ကားအတွက် သတ်မှတ်ထားသောစျေးနှုန်း မရှိသေးပါ။ Admin ကို ဆက်သွယ်ပါ။"
    return format_mmk(price)
