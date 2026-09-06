"""
app/utils/validation.py

Input validation helpers shared across handlers.
"""
from __future__ import annotations

from typing import Optional

from app.utils.numbers import parse_myanmar_int
from app.utils.pricing import is_valid_package


def validate_package_input(text: str) -> Optional[int]:
    """
    Validate a user-supplied package quantity string.

    Returns the integer quantity if it's a configured package,
    or None if invalid.
    """
    quantity = parse_myanmar_int(text)
    if quantity is None:
        return None
    if not is_valid_package(quantity):
        return None
    return quantity
