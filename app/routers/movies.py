import asyncio
import logging

from fastapi import APIRouter, Query, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.movie import MovieBrief, MovieDetail, MovieListResponse, CastMember, VideoResult, GenreResponse
from app.services.tmdb_client import tmdb_client
from app.services.mood_mapper import MOOD_MAP
from app.services.cache_service import cache_movie
from app.utils.dependencies import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/movies", tags=["movies"])


def _parse_movie_brief(movie: dict) -> MovieBrief:
    return MovieBrief(
        tmdb_id=movie.get("id", 0),
        title=movie.get("title", ""),
        poster_path=movie.get("poster_path"),
        backdrop_path=movie.get("backdrop_path"),
        release_date=movie.get("release_date") or None,
        vote_average=movie.get("vote_average", 0),
        genre_ids=movie.get("genre_ids", []),
        popularity=movie.get("popularity", 0),
    )


def _parse_movie_list(data: dict | None) -> MovieListResponse:
    if not data:
        return MovieListResponse(page=1, total_pages=0, total_results=0, results=[])

    return MovieListResponse(
        page=data.get("page", 1),
        total_pages=data.get("total_pages", 0),
        total_results=data.get("total_results", 0),
        results=[_parse_movie_brief(m) for m in data.get("results", [])],
    )


@router.get("/trending", response_model=MovieListResponse)
async def get_trending(page: int = Query(1, ge=1)):
    data = await tmdb_client.get_trending(page)
    return _parse_movie_list(data)


@router.get("/popular", response_model=MovieListResponse)
async def get_popular(page: int = Query(1, ge=1)):
    data = await tmdb_client.get_popular(page)
    return _parse_movie_list(data)


@router.get("/top-rated", response_model=MovieListResponse)
async def get_top_rated(page: int = Query(1, ge=1)):
    data = await tmdb_client.get_top_rated(page)
    return _parse_movie_list(data)


@router.get("/upcoming", response_model=MovieListResponse)
async def get_upcoming(page: int = Query(1, ge=1)):
    data = await tmdb_client.get_upcoming(page)
    return _parse_movie_list(data)


@router.get("/now-playing", response_model=MovieListResponse)
async def get_now_playing(page: int = Query(1, ge=1)):
    data = await tmdb_client.get_now_playing(page)
    return _parse_movie_list(data)


@router.get("/search", response_model=MovieListResponse)
async def search_movies(q: str = Query(min_length=2), page: int = Query(1, ge=1)):
    data = await tmdb_client.search_movies(q, page)
    return _parse_movie_list(data)


@router.get("/genre/{genre_id}", response_model=MovieListResponse)
async def get_by_genre(genre_id: int, page: int = Query(1, ge=1)):
    data = await tmdb_client.discover_by_genres([genre_id], page)
    return _parse_movie_list(data)


@router.get("/genres", response_model=list[GenreResponse])
async def get_genres():
    data = await tmdb_client.get_genres()
    if not data or "genres" not in data:
        return []
    return [GenreResponse(id=g["id"], name=g["name"]) for g in data["genres"]]


@router.get("/discover")
async def discover_by_mood(mood: str = Query(...)):
    mood_lower = mood.lower()
    if mood_lower not in MOOD_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown mood: {mood}. Available: {', '.join(MOOD_MAP.keys())}",
        )

    mood_config = MOOD_MAP[mood_lower]
    data = await tmdb_client.discover_by_genres(mood_config["genres"])
    return _parse_movie_list(data)


@router.get("/{tmdb_id}", response_model=MovieDetail)
async def get_movie_detail(
    tmdb_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    data = await tmdb_client.get_movie_details(tmdb_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found",
        )

    # Parse cast
    cast = []
    credits = data.get("credits", {})
    for member in credits.get("cast", [])[:15]:
        cast.append(CastMember(
            id=member.get("id", 0),
            name=member.get("name", ""),
            character=member.get("character", ""),
            profile_path=member.get("profile_path"),
        ))

    # Parse videos (trailers)
    videos = []
    for video in data.get("videos", {}).get("results", []):
        if video.get("site") == "YouTube":
            videos.append(VideoResult(
                key=video.get("key", ""),
                name=video.get("name", ""),
                site=video.get("site", ""),
                type=video.get("type", ""),
            ))

    # Parse genres
    genres = [GenreResponse(id=g["id"], name=g["name"]) for g in data.get("genres", [])]

    # Auto-cache on view for ML engine (background, non-blocking)
    background_tasks.add_task(cache_movie, db, tmdb_id)

    return MovieDetail(
        tmdb_id=data.get("id", 0),
        title=data.get("title", ""),
        overview=data.get("overview"),
        poster_path=data.get("poster_path"),
        backdrop_path=data.get("backdrop_path"),
        release_date=data.get("release_date") or None,
        vote_average=data.get("vote_average", 0),
        vote_count=data.get("vote_count", 0),
        genres=genres,
        runtime=data.get("runtime"),
        tagline=data.get("tagline"),
        popularity=data.get("popularity", 0),
        original_language=data.get("original_language"),
        cast=cast,
        videos=videos,
    )
