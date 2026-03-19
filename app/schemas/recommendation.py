from pydantic import BaseModel

from app.schemas.movie import MovieBrief


class RecommendationResponse(BaseModel):
    source: str  # "ml", "tmdb", "mood", "personalized"
    title: str  # e.g. "Because you liked Inception"
    movies: list[MovieBrief]
