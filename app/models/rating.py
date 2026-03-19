import uuid
from datetime import datetime

from sqlalchemy import Integer, Float, ForeignKey, UniqueConstraint, DateTime, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRating(Base):
    __tablename__ = "user_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tmdb_id: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "tmdb_id"),
        CheckConstraint("rating >= 0.5 AND rating <= 5.0", name="rating_range"),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="ratings")
