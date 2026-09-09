"""
tests/test_session_service.py
────────────────────────────────────────────────────────────────────────
QA Tests for Session Service & MongoDB State Machine.
"""

import pytest
from app.models.session import SessionState
from app.services.session_service import session_service


@pytest.mark.asyncio
async def test_session_lifecycle(clean_db):
    telegram_id = 1122334455

    # 1. Get empty session
    session = await session_service.get_session(telegram_id)
    assert session is None or session.state == SessionState.IDLE

    # 2. Set state to SELECTING_PACKAGE
    sess = await session_service.set_state(
        telegram_id=telegram_id,
        state=SessionState.SELECTING_PACKAGE,
        package_size=3,
        selected_movie_ids=["m1", "m2"]
    )
    assert sess.state == SessionState.SELECTING_PACKAGE
    assert sess.packageSize == 3
    assert len(sess.selectedMovieIds) == 2

    # 3. Clear session
    cleared = await session_service.clear_session(telegram_id)
    assert cleared.state == SessionState.IDLE
    assert len(cleared.selectedMovieIds) == 0
