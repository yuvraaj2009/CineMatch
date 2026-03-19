import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movie import MovieCache
from app.services.tmdb_client import tmdb_client

logger = logging.getLogger(__name__)


async def cache_movie(db: AsyncSession, tmdb_id: int) -> MovieCache | None:
    """Fetch movie from TMDB and upsert into movies_cache.

    Called when a user rates, adds to list, or views a movie detail.
    Returns the cached record, or None if TMDB fetch failed.
    """
    # Check if already cached and fresh (< 7 days old)
    result = await db.execute(
        select(MovieCache).where(MovieCache.tmdb_id == tmdb_id)
    )
    cached = result.scalar_one_or_none()

    if cached and cached.cached_at > datetime.now(timezone.utc) - timedelta(days=7):
        return cached

    # Fetch full details from TMDB (includes credits, videos, keywords)
    movie_data = await tmdb_client.get_movie_details(tmdb_id)
    if not movie_data:
        logger.warning(f"Failed to fetch TMDB data for movie {tmdb_id}")
        return cached  # Return stale cache if available

    # Extract genres and keywords as string lists for ML
    genres = [g["name"] for g in movie_data.get("genres", [])]
    keywords_raw = movie_data.get("keywords", {})
    keywords = [k["name"] for k in keywords_raw.get("keywords", [])]

    # Parse release_date safely
    release_date = None
    rd = movie_data.get("release_date")
    if rd:
        try:
            from datetime import date

            parts = rd.split("-")
            if len(parts) == 3:
                release_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            pass

    if cached:
        # Update existing record
        cached.title = movie_data.get("title", cached.title)
        cached.overview = movie_data.get("overview")
        cached.poster_path = movie_data.get("poster_path")
        cached.backdrop_path = movie_data.get("backdrop_path")
        cached.release_date = release_date
        cached.vote_average = movie_data.get("vote_average", 0)
        cached.vote_count = movie_data.get("vote_count", 0)
        cached.genres = genres
        cached.runtime = movie_data.get("runtime")
        cached.tagline = movie_data.get("tagline")
        cached.keywords = keywords
        cached.popularity = movie_data.get("popularity", 0)
        cached.original_language = movie_data.get("original_language")
        cached.cached_at = datetime.now(timezone.utc)
    else:
        # Insert new record
        cached = MovieCache(
            tmdb_id=tmdb_id,
            title=movie_data.get("title", ""),
            overview=movie_data.get("overview"),
            poster_path=movie_data.get("poster_path"),
            backdrop_path=movie_data.get("backdrop_path"),
            release_date=release_date,
            vote_average=movie_data.get("vote_average", 0),
            vote_count=movie_data.get("vote_count", 0),
            genres=genres,
            runtime=movie_data.get("runtime"),
            tagline=movie_data.get("tagline"),
            keywords=keywords,
            popularity=movie_data.get("popularity", 0),
            original_language=movie_data.get("original_language"),
        )
        db.add(cached)

    await db.commit()
    await db.refresh(cached)
    logger.debug(f"Cached movie {tmdb_id}: {cached.title}")
    return cached


async def get_all_cached_movies(db: AsyncSession) -> list[dict]:
    """Return all cached movies as dicts suitable for ML matrix building."""
    result = await db.execute(select(MovieCache))
    rows = result.scalars().all()

    return [
        {
            "tmdb_id": m.tmdb_id,
            "overview": m.overview or "",
            "genres": m.genres if isinstance(m.genres, list) else [],
            "keywords": m.keywords if isinstance(m.keywords, list) else [],
            "tagline": m.tagline or "",
        }
        for m in rows
    ]


async def get_movies_by_ids(db: AsyncSession, tmdb_ids: list[int]) -> list[dict]:
    """Fetch cached movies by tmdb_ids, preserving order. Returns brief dicts."""
    if not tmdb_ids:
        return []

    result = await db.execute(
        select(MovieCache).where(MovieCache.tmdb_id.in_(tmdb_ids))
    )
    rows = {m.tmdb_id: m for m in result.scalars().all()}

    movies = []
    for tid in tmdb_ids:
        m = rows.get(tid)
        if m:
            movies.append({
                "tmdb_id": m.tmdb_id,
                "title": m.title,
                "poster_path": m.poster_path,
                "backdrop_path": m.backdrop_path,
                "release_date": str(m.release_date) if m.release_date else None,
                "vote_average": m.vote_average,
                "genre_ids": [],
                "popularity": m.popularity,
            })

    return movies
