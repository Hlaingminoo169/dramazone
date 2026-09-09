"""
app/models/audit_log.py
─────────────────────────────────────────────────────────────────────────────
Admin action audit log model.

Purpose (req #5)
-----------------
Every important admin action is recorded in the `audit_logs` collection.
This creates an auditable trail so that:
- It is always clear which admin approved/rejected an order (req #6, #38)
- Admin actions can be reviewed if a dispute arises
- Suspicious admin activity can be detected

The audit log is append-only — existing records are never modified.

What is logged
--------------
  ORDER_APPROVED   — admin confirmed customer payment
  ORDER_REJECTED   — admin rejected customer payment (with reason)
  ORDER_VIEWED     — admin opened an order for review
  MOVIE_CREATED    — admin added a new movie to the catalog
  MOVIE_UPDATED    — admin updated movie details or watch link
  MOVIE_DISABLED   — admin disabled a movie (soft delete)
  SETTING_UPDATED  — admin changed a bot setting

What is stored per record (req #5)
------------------------------------
  adminTelegramId  — permanent, never changes
  adminUsername    — snapshot at time of action (may change later)
  adminFirstName   — snapshot at time of action
  action           — AuditAction enum value
  timestamp        — UTC datetime
  orderCode        — for order-related actions
  metadata         — any additional context (rejection reason, field changes etc.)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AuditAction(str, Enum):
    """Enumeration of all auditable admin actions."""

    # Order management
    ORDER_APPROVED = "ORDER_APPROVED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_VIEWED = "ORDER_VIEWED"

    # Content management
    MOVIE_CREATED = "MOVIE_CREATED"
    MOVIE_UPDATED = "MOVIE_UPDATED"
    MOVIE_DISABLED = "MOVIE_DISABLED"

    # Configuration
    SETTING_UPDATED = "SETTING_UPDATED"


class AuditLog(BaseModel):
    """
    Single admin audit log entry as stored in MongoDB.

    Append-only — never updated after creation.
    """

    # ── Who ──────────────────────────────────────────
    adminTelegramId: int = Field(
        ...,
        description="Admin's permanent Telegram user ID",
    )
    adminUsername: Optional[str] = Field(
        default=None,
        description="Admin's @username at the time of action (snapshot)",
    )
    adminFirstName: str = Field(
        ...,
        description="Admin's first name at the time of action (snapshot)",
    )

    # ── What ─────────────────────────────────────────
    action: AuditAction = Field(
        ...,
        description="The type of admin action performed",
    )

    # ── Context ──────────────────────────────────────
    orderCode: Optional[str] = Field(
        default=None,
        description="Related order code, for order-related actions",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Optional additional context. Examples: "
            "{'rejectionReason': '...'} for ORDER_REJECTED, "
            "{'changedFields': [...]} for MOVIE_UPDATED"
        ),
    )

    # ── When ─────────────────────────────────────────
    timestamp: datetime = Field(
        ...,
        description="UTC datetime when the action was performed",
    )

    # ──────────────────────────────────────────────
    # Derived helpers
    # ──────────────────────────────────────────────
    @property
    def admin_display(self) -> str:
        """
        Display string for the admin who performed this action (req #6, #38).

        Returns '@username' if available, otherwise 'First Name'.
        """
        if self.adminUsername:
            return f"@{self.adminUsername}"
        return self.adminFirstName
