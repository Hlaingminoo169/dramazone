"""
tests/test_order_service.py
────────────────────────────────────────────────────────────────────────
QA Edge Case Tests for Order Lifecycle & State Transitions.
"""

import pytest
from app.models.order import OrderStatus
from app.services.order_service import order_service


@pytest.mark.asyncio
async def test_order_creation_validation(clean_db):
    telegram_id = 99887766

    # Test valid package size creation (1, 3, 5)
    order = await order_service.create_order(
        telegram_id=telegram_id,
        package_size=3,
        movie_ids=["m1", "m2", "m3"]
    )
    assert order.packageSize == 3
    assert order.totalPrice == 3500
    assert order.status == OrderStatus.PENDING_PAYMENT

    # Test invalid package size rejection
    with pytest.raises(ValueError, match="မရှိပါ"):
        await order_service.create_order(
            telegram_id=telegram_id,
            package_size=2,
            movie_ids=["m1", "m2"]
        )


@pytest.mark.asyncio
async def test_duplicate_screenshot_submission_prevention(clean_db):
    telegram_id = 88776655
    order = await order_service.create_order(
        telegram_id=telegram_id,
        package_size=1,
        movie_ids=["m1"]
    )

    # First submission -> SUCCESS
    ok1, msg1 = await order_service.submit_screenshot(
        order_id=str(order.id),
        telegram_id=telegram_id,
        file_id="proof_photo_1"
    )
    assert ok1 is True

    # Second submission on already submitted order -> REJECTED (Atomic Protection)
    ok2, msg2 = await order_service.submit_screenshot(
        order_id=str(order.id),
        telegram_id=telegram_id,
        file_id="proof_photo_2"
    )
    assert ok2 is False
    assert "အတည်ပြုနေပြီး" in msg2 or "မရှိပါ" in msg2
