"""
app/models/movie.py
─────────────────────────────────────────────────────────────────────────────
VIP movie / content catalog model.

Notes
-----
- `watchLink` is the actual VIP content URL sent to approved customers.
  It must NEVER be sent to a user before their order is approved (req #27).
- `price` is the base per-movie price used for reference and revenue attribution
  in reports (req #15).  The actual order total is determined by the package
  tier price from config, not by summing individual movie prices.
- `isActive` allows admins to disable a movie without deleting it —
  order history referencing the movie remains intact (req #7).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class Movie(BaseModel):
    """
    VIP movie / content entry as stored in MongoDB.

    The `_id` field (MongoDB ObjectId as string) is the canonical reference
    used in Order.movieIds lists.
    """

    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Primary display title (Myanmar language preferred)",
    )
    titleEn: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional English title for admin search",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional synopsis or description shown in the customer bot",
    )
    watchLink: str = Field(
        ...,
        description=(
            "VIP content URL. "
            "ONLY sent to customers after order approval (req #27). "
            "Never exposed in pending/rejected states."
        ),
    )
    price: int = Field(
        ...,
        gt=0,
        description=(
            "Base per-movie price in MMK. "
            "Used for revenue attribution in movie sales reports (req #15). "
            "Actual order total uses the package tier price from config."
        ),
    )
    isActive: bool = Field(
        default=True,
        description="False = disabled; hidden from customers but history preserved",
    )

    # Lifecycle timestamps (UTC, displayed in configured TZ — req #37)
    createdAt: datetime = Field(
        ...,
        description="UTC datetime when this movie was added to the catalog",
    )
    updatedAt: datetime = Field(
        ...,
        description="UTC datetime of the most recent update",
    )
