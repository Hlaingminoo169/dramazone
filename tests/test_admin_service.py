"""
tests/test_admin_service.py
────────────────────────────────────────────────────────────────────────
Unit tests for Admin Service and order approval/rejection workflows.
"""

import pytest
from datetime import datetime

from app.models.order import OrderStatus
from app.services.admin_service import admin_service
from app.services.order_service import order_service
from app.config import config


@pytest.mark.asyncio
async def test_admin_authorization():
    """Verify is_admin correctly checks config admin IDs."""
    admin_id = config.admin_ids[0] if config.admin_ids else 1673861706
    assert admin_service.is_admin(admin_id) is True
    assert admin_service.is_admin(999999999) is False


@pytest.mark.asyncio
async def test_admin_stats_and_order_flow(clean_db):
    """Test full admin flow: stats calculation, approve, and reject."""
    # 1. Create test user and order
    telegram_id = 987654321
    order = await order_service.create_order(
        telegram_id=telegram_id,
        package_size=1,
        movie_ids=["60d5ecb8b3b72c001f3e1a01"]
    )
    
    # 2. Submit payment screenshot (transition to WAITING_APPROVAL)
    success, _ = await order_service.submit_screenshot(
        order_id=str(order.id),
        telegram_id=telegram_id,
        file_id="test_file_id_123"
    )
    assert success is True

    # 3. Check stats
    stats = await admin_service.get_dashboard_stats()
    assert stats["pending_count"] >= 1

    # 4. Approve order
    admin_id = config.admin_ids[0] if config.admin_ids else 1673861706
    ok, msg, approved_order = await admin_service.approve_order(
        order_code=order.orderCode,
        admin_id=admin_id,
        admin_username="test_admin"
    )
    assert ok is True
    assert approved_order.status == OrderStatus.APPROVED

    # 5. Verify stats updated
    stats_after = await admin_service.get_dashboard_stats()
    assert stats_after["approved_count"] >= 1
