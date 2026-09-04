"""
app/utils/validation.py
=======================
Input validation helpers shared across handlers.
"""

from __future__ import annotations

from bson import ObjectId


def is_valid_object_id(value: str) -> bool:
    """Return True if value is a valid MongoDB ObjectId hex string."""
    try:
        ObjectId(value)
        return True
    except Exception:
        return False


def sanitize_callback_data(data: str | None) -> str | None:
    """
    Strip and return callback data, or None if empty/None.
    Prevents empty string from being passed into handlers.
    """
    if not data:
        return None
    stripped = data.strip()
    return stripped if stripped else None
