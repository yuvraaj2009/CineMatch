import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.rating import UserRating
from app.schemas.rating import RatingCreate, RatingUpdate, RatingResponse
from app.services.cache_service import cache_movie
from app.utils.dependencies import get_db, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ratings", tags=["ratings"])


@router.get("", response_model=list[RatingResponse])
async def get_user_ratings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserRating)
        .where(UserRating.user_id == current_user.id)
        .order_by(UserRating.created_at.desc())
    )
    return result.scalars().all()


@router.post("/{tmdb_id}", response_model=RatingResponse, status_code=status.HTTP_201_CREATED)
async def rate_movie(
    tmdb_id: int,
    data: RatingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Check if already rated
    existing = await db.execute(
        select(UserRating).where(
            UserRating.user_id == current_user.id, UserRating.tmdb_id == tmdb_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie already rated. Use PUT to update.",
        )

    rating = UserRating(
        user_id=current_user.id,
        tmdb_id=tmdb_id,
        rating=data.rating,
    )
    db.add(rating)
    await db.commit()
    await db.refresh(rating)

    # Auto-cache movie for ML engine
    await cache_movie(db, tmdb_id)

    return rating


@router.put("/{tmdb_id}", response_model=RatingResponse)
async def update_rating(
    tmdb_id: int,
    data: RatingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserRating).where(
            UserRating.user_id == current_user.id, UserRating.tmdb_id == tmdb_id
        )
    )
    rating = result.scalar_one_or_none()

    if not rating:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating not found")

    rating.rating = data.rating
    await db.commit()
    await db.refresh(rating)

    return rating


@router.delete("/{tmdb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rating(
    tmdb_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserRating).where(
            UserRating.user_id == current_user.id, UserRating.tmdb_id == tmdb_id
        )
    )
    rating = result.scalar_one_or_none()

    if not rating:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating not found")

    await db.delete(rating)
    await db.commit()
