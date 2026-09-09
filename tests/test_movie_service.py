"""
tests/test_movie_service.py
────────────────────────────────────────────────────────────────────────
QA Tests for Movie Service & Security Link Protection.
"""

import pytest
from app.services.movie_service import movie_service


@pytest.mark.asyncio
async def test_movie_catalog_and_link_security(clean_db):
    # 1. Fetch active movies
    movies = await movie_service.get_active_movies()
    assert isinstance(movies, list)

    if movies:
        m_id = str(movies[0].id)

        # Default query should NOT include sensitive watchLink for security (req #18)
        unprotected_movies = await movie_service.get_movies_by_ids([m_id], include_watch_link=False)
        assert len(unprotected_movies) == 1
        assert unprotected_movies[0].watchLink is None or unprotected_movies[0].watchLink == ""

        # Approved delivery query SHOULD include watchLink
        protected_movies = await movie_service.get_movies_by_ids([m_id], include_watch_link=True)
        assert len(protected_movies) == 1
        assert protected_movies[0].watchLink is not None
