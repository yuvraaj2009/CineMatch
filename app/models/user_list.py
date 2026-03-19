import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserList(Base):
    __tablename__ = "user_lists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="lists")
    movies: Mapped[list["UserListMovie"]] = relationship(
        "UserListMovie", back_populates="list", cascade="all, delete-orphan"
    )


class UserListMovie(Base):
    __tablename__ = "user_list_movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_lists.id", ondelete="CASCADE"), nullable=False
    )
    tmdb_id: Mapped[int] = mapped_column(Integer, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("list_id", "tmdb_id"),)

    # Relationships
    list: Mapped["UserList"] = relationship("UserList", back_populates="movies")
