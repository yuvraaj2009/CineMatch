import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.user_list import UserList, UserListMovie
from app.schemas.user_list import (
    ListCreate,
    ListUpdate,
    ListMovieAdd,
    ListResponse,
    ListDetailResponse,
    ListMovieResponse,
)
from app.services.cache_service import cache_movie
from app.utils.dependencies import get_db, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lists", tags=["lists"])


@router.get("", response_model=list[ListResponse])
async def get_user_lists(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(
            UserList,
            func.count(UserListMovie.id).label("movie_count"),
        )
        .outerjoin(UserListMovie, UserList.id == UserListMovie.list_id)
        .where(UserList.user_id == current_user.id)
        .group_by(UserList.id)
        .order_by(UserList.is_default.desc(), UserList.created_at)
    )
    rows = result.all()

    return [
        ListResponse(
            id=user_list.id,
            name=user_list.name,
            description=user_list.description,
            is_default=user_list.is_default,
            created_at=user_list.created_at,
            movie_count=movie_count,
        )
        for user_list, movie_count in rows
    ]


@router.post("", response_model=ListResponse, status_code=status.HTTP_201_CREATED)
async def create_list(
    data: ListCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_list = UserList(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
    )
    db.add(user_list)
    await db.commit()
    await db.refresh(user_list)

    return ListResponse(
        id=user_list.id,
        name=user_list.name,
        description=user_list.description,
        is_default=user_list.is_default,
        created_at=user_list.created_at,
        movie_count=0,
    )


@router.get("/{list_id}", response_model=ListDetailResponse)
async def get_list_detail(
    list_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserList)
        .options(selectinload(UserList.movies))
        .where(UserList.id == list_id, UserList.user_id == current_user.id)
    )
    user_list = result.scalar_one_or_none()

    if not user_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="List not found")

    return ListDetailResponse(
        id=user_list.id,
        name=user_list.name,
        description=user_list.description,
        is_default=user_list.is_default,
        created_at=user_list.created_at,
        movie_count=len(user_list.movies),
        movies=[
            ListMovieResponse(tmdb_id=m.tmdb_id, added_at=m.added_at)
            for m in user_list.movies
        ],
    )


@router.put("/{list_id}", response_model=ListResponse)
async def update_list(
    list_id: uuid.UUID,
    data: ListUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserList).where(UserList.id == list_id, UserList.user_id == current_user.id)
    )
    user_list = result.scalar_one_or_none()

    if not user_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="List not found")

    if user_list.is_default:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify default lists",
        )

    if data.name is not None:
        user_list.name = data.name
    if data.description is not None:
        user_list.description = data.description

    await db.commit()
    await db.refresh(user_list)

    # Get movie count
    count_result = await db.execute(
        select(func.count(UserListMovie.id)).where(UserListMovie.list_id == list_id)
    )
    movie_count = count_result.scalar() or 0

    return ListResponse(
        id=user_list.id,
        name=user_list.name,
        description=user_list.description,
        is_default=user_list.is_default,
        created_at=user_list.created_at,
        movie_count=movie_count,
    )


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_list(
    list_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserList).where(UserList.id == list_id, UserList.user_id == current_user.id)
    )
    user_list = result.scalar_one_or_none()

    if not user_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="List not found")

    if user_list.is_default:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete default lists",
        )

    await db.delete(user_list)
    await db.commit()


@router.post("/{list_id}/movies", status_code=status.HTTP_201_CREATED)
async def add_movie_to_list(
    list_id: uuid.UUID,
    data: ListMovieAdd,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify list belongs to user
    result = await db.execute(
        select(UserList).where(UserList.id == list_id, UserList.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="List not found")

    # Check if movie already in list
    existing = await db.execute(
        select(UserListMovie).where(
            UserListMovie.list_id == list_id, UserListMovie.tmdb_id == data.tmdb_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie already in list",
        )

    movie_entry = UserListMovie(list_id=list_id, tmdb_id=data.tmdb_id)
    db.add(movie_entry)
    await db.commit()

    # Auto-cache movie for ML engine
    await cache_movie(db, data.tmdb_id)

    return {"message": "Movie added to list"}


@router.delete("/{list_id}/movies/{tmdb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_movie_from_list(
    list_id: uuid.UUID,
    tmdb_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify list belongs to user
    result = await db.execute(
        select(UserList).where(UserList.id == list_id, UserList.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="List not found")

    result = await db.execute(
        select(UserListMovie).where(
            UserListMovie.list_id == list_id, UserListMovie.tmdb_id == tmdb_id
        )
    )
    movie_entry = result.scalar_one_or_none()

    if not movie_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not in list")

    await db.delete(movie_entry)
    await db.commit()
