import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.rating import UserRating
from app.schemas.movie import MovieBrief
from app.schemas.recommendation import RecommendationResponse
from app.services.tmdb_client import tmdb_client
from app.services.cache_service import get_movies_by_ids
from app.utils.dependencies import get_db, get_current_user
from ml.recommender import get_recommender

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _parse_movie_brief(movie: dict) -> MovieBrief:
    return MovieBrief(
        tmdb_id=movie.get("id", movie.get("tmdb_id", 0)),
        title=movie.get("title", ""),
        poster_path=movie.get("poster_path"),
        backdrop_path=movie.get("backdrop_path"),
        release_date=movie.get("release_date") or None,
        vote_average=movie.get("vote_average", 0),
        genre_ids=movie.get("genre_ids", []),
        popularity=movie.get("popularity", 0),
    )


async def _cached_movies_to_briefs(db: AsyncSession, tmdb_ids: list[int]) -> list[MovieBrief]:
    """Convert cached movie IDs to MovieBrief list."""
    cached = await get_movies_by_ids(db, tmdb_ids)
    return [_parse_movie_brief(m) for m in cached]


@router.get("/similar/{tmdb_id}", response_model=RecommendationResponse)
async def get_similar_movies(tmdb_id: int, db: AsyncSession = Depends(get_db)):
    recommender = get_recommender()

    # Try ML first
    if recommender.is_ready:
        similar_ids = recommender.get_similar(tmdb_id)
        if similar_ids:
            movies = await _cached_movies_to_briefs(db, similar_ids)
            if movies:
                return RecommendationResponse(
                    source="ml",
                    title="Similar Movies",
                    movies=movies,
                )

    # Fallback: TMDB recommendations
    data = await tmdb_client.get_tmdb_recommendations(tmdb_id)

    if not data or not data.get("results"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No recommendations found",
        )

    movies = [_parse_movie_brief(m) for m in data["results"][:20]]

    return RecommendationResponse(
        source="tmdb",
        title="Similar Movies",
        movies=movies,
    )


@router.get("/because-you-liked/{tmdb_id}", response_model=RecommendationResponse)
async def because_you_liked(tmdb_id: int, db: AsyncSession = Depends(get_db)):
    # Get movie title for the label
    details = await tmdb_client.get_movie_details(tmdb_id)
    movie_title = details.get("title", "this movie") if details else "this movie"

    recommender = get_recommender()

    # Try ML first
    if recommender.is_ready:
        similar_ids = recommender.get_similar(tmdb_id)
        if similar_ids:
            movies = await _cached_movies_to_briefs(db, similar_ids)
            if movies:
                return RecommendationResponse(
                    source="ml",
                    title=f"Because you liked {movie_title}",
                    movies=movies,
                )

    # Fallback: TMDB recommendations
    data = await tmdb_client.get_tmdb_recommendations(tmdb_id)

    if not data or not data.get("results"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No recommendations found",
        )

    movies = [_parse_movie_brief(m) for m in data["results"][:20]]

    return RecommendationResponse(
        source="tmdb",
        title=f"Because you liked {movie_title}",
        movies=movies,
    )


@router.get("/personalized", response_model=RecommendationResponse)
async def get_personalized(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    recommender = get_recommender()

    # Get user's ratings as {tmdb_id: score}
    result = await db.execute(
        select(UserRating).where(UserRating.user_id == current_user.id)
    )
    user_ratings = {r.tmdb_id: r.rating for r in result.scalars().all()}

    # Try ML-powered personalized recs
    if user_ratings and recommender.is_ready:
        rec_ids = recommender.get_personalized(user_ratings)
        if rec_ids:
            movies = await _cached_movies_to_briefs(db, rec_ids)
            if movies:
                return RecommendationResponse(
                    source="ml",
                    title="Recommended For You",
                    movies=movies,
                )

    # Fallback: trending movies
    data = await tmdb_client.get_trending()

    if not data or not data.get("results"):
        return RecommendationResponse(
            source="tmdb",
            title="Recommended For You",
            movies=[],
        )

    movies = [_parse_movie_brief(m) for m in data["results"][:20]]

    return RecommendationResponse(
        source="tmdb",
        title="Recommended For You",
        movies=movies,
    )
