"""
app/utils/order_code.py

Human-friendly order code generation.

Format:  DZ-YYYYMMDD-XXXX
  DZ     → DramaZone prefix
  YYYYMMDD → UTC date
  XXXX   → 4 random uppercase alphanumeric characters

Example: DZ-20260905-AB12

Collision probability is negligible for the expected order volume.
If a collision occurs (unique index violation), callers should retry.
"""
from __future__ import annotations

import random
import string
from datetime import datetime, timezone


_CHARSET = string.ascii_uppercase + string.digits  # A-Z 0-9


def generate_order_code() -> str:
    """
    Generate a new human-readable unique order code.

    Example return value:  "DZ-20260905-AB12"
    """
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = "".join(random.choices(_CHARSET, k=4))
    return f"DZ-{date_part}-{random_part}"
