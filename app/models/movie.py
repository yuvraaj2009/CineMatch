from datetime import date, datetime

from sqlalchemy import Integer, String, Text, Float, Date, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MovieCache(Base):
    __tablename__ = "movies_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tmdb_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    backdrop_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    vote_average: Mapped[float] = mapped_column(Float, default=0)
    vote_count: Mapped[int] = mapped_column(Integer, default=0)
    genres: Mapped[dict] = mapped_column(JSONB, default=list)
    runtime: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tagline: Mapped[str | None] = mapped_column(String(500), nullable=True)
    keywords: Mapped[dict] = mapped_column(JSONB, default=list)
    popularity: Mapped[float] = mapped_column(Float, default=0, index=True)
    original_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cached_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tmdb_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
