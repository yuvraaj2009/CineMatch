from datetime import datetime

from pydantic import BaseModel, Field


class RatingCreate(BaseModel):
    rating: float = Field(ge=0.5, le=5.0)


class RatingUpdate(BaseModel):
    rating: float = Field(ge=0.5, le=5.0)


class RatingResponse(BaseModel):
    tmdb_id: int
    rating: float
    created_at: datetime

    model_config = {"from_attributes": True}
