"""
app/utils/order_code.py
=======================
Human-readable, unique order code generator.
Format: ORD-XXXX where XXXX is a zero-padded random 4-digit number.
Collision-safe via MongoDB unique index on orderCode.
"""

from __future__ import annotations

import random
import string


def generate_order_code() -> str:
    """
    Generate a random order code like ORD-4821.
    MongoDB's unique index on orderCode guarantees no duplicates.
    """
    digits = "".join(random.choices(string.digits, k=4))
    return f"ORD-{digits}"
