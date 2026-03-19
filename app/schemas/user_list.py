import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ListCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class ListUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class ListMovieAdd(BaseModel):
    tmdb_id: int


class ListMovieResponse(BaseModel):
    tmdb_id: int
    added_at: datetime

    model_config = {"from_attributes": True}


class ListResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_default: bool
    created_at: datetime
    movie_count: int = 0

    model_config = {"from_attributes": True}


class ListDetailResponse(ListResponse):
    movies: list[ListMovieResponse] = []
