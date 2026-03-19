from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/movie_recommender_db"

    @property
    def async_database_url(self) -> str:
        """Ensure the URL uses the asyncpg driver, regardless of how it's provided."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    # TMDB
    TMDB_API_KEY: str = ""
    TMDB_BASE_URL: str = "https://api.themoviedb.org/3"

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REMEMBER_ME_EXPIRE_DAYS: int = 30

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,https://cinematch-web-tan.vercel.app"

    # Environment
    ENVIRONMENT: str = "development"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
