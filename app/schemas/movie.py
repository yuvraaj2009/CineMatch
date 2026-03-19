from datetime import date

from pydantic import BaseModel


class GenreResponse(BaseModel):
    id: int
    name: str


class MovieBrief(BaseModel):
    tmdb_id: int
    title: str
    poster_path: str | None
    backdrop_path: str | None
    release_date: date | None
    vote_average: float
    genre_ids: list[int] = []
    popularity: float = 0

    model_config = {"from_attributes": True}


class CastMember(BaseModel):
    id: int
    name: str
    character: str
    profile_path: str | None


class VideoResult(BaseModel):
    key: str
    name: str
    site: str
    type: str


class MovieDetail(BaseModel):
    tmdb_id: int
    title: str
    overview: str | None
    poster_path: str | None
    backdrop_path: str | None
    release_date: date | None
    vote_average: float
    vote_count: int
    genres: list[GenreResponse] = []
    runtime: int | None
    tagline: str | None
    popularity: float = 0
    original_language: str | None
    cast: list[CastMember] = []
    videos: list[VideoResult] = []


class MovieListResponse(BaseModel):
    page: int
    total_pages: int
    total_results: int
    results: list[MovieBrief]


class SearchResult(BaseModel):
    tmdb_id: int
    title: str
    poster_path: str | None
    release_date: date | None
    vote_average: float
    overview: str | None
