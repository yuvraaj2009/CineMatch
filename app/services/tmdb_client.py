import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TMDBClient:
    """Async wrapper for TMDB API v3."""

    def __init__(self):
        self.base_url = settings.TMDB_BASE_URL
        self.api_key = settings.TMDB_API_KEY
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                params={"api_key": self.api_key},
                timeout=15.0,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _get(self, endpoint: str, params: dict | None = None) -> dict[str, Any] | None:
        try:
            client = await self._get_client()
            response = await client.get(endpoint, params=params or {})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"TMDB API error {e.response.status_code}: {endpoint}")
            return None
        except httpx.RequestError as e:
            logger.error(f"TMDB request failed: {e}")
            return None

    # --- Movie Lists ---

    async def get_trending(self, page: int = 1) -> dict[str, Any] | None:
        return await self._get("/trending/movie/week", {"page": page})

    async def get_popular(self, page: int = 1) -> dict[str, Any] | None:
        return await self._get("/movie/popular", {"page": page})

    async def get_top_rated(self, page: int = 1) -> dict[str, Any] | None:
        return await self._get("/movie/top_rated", {"page": page})

    async def get_upcoming(self, page: int = 1) -> dict[str, Any] | None:
        return await self._get("/movie/upcoming", {"page": page})

    async def get_now_playing(self, page: int = 1) -> dict[str, Any] | None:
        return await self._get("/movie/now_playing", {"page": page})

    # --- Movie Details ---

    async def get_movie_details(self, tmdb_id: int) -> dict[str, Any] | None:
        return await self._get(
            f"/movie/{tmdb_id}",
            {"append_to_response": "credits,videos,keywords"},
        )

    # --- Search ---

    async def search_movies(self, query: str, page: int = 1) -> dict[str, Any] | None:
        return await self._get("/search/movie", {"query": query, "page": page})

    # --- Discovery ---

    async def discover_by_genres(
        self, genre_ids: list[int], page: int = 1, sort_by: str = "popularity.desc"
    ) -> dict[str, Any] | None:
        return await self._get(
            "/discover/movie",
            {
                "with_genres": ",".join(str(g) for g in genre_ids),
                "sort_by": sort_by,
                "page": page,
            },
        )

    async def discover_by_keywords(
        self, keywords: str, genre_ids: list[int] | None = None, page: int = 1
    ) -> dict[str, Any] | None:
        params: dict[str, Any] = {
            "with_keywords": keywords,
            "sort_by": "popularity.desc",
            "page": page,
        }
        if genre_ids:
            params["with_genres"] = ",".join(str(g) for g in genre_ids)
        return await self._get("/discover/movie", params)

    # --- Genres ---

    async def get_genres(self) -> dict[str, Any] | None:
        return await self._get("/genre/movie/list")

    # --- TMDB Recommendations (fallback) ---

    async def get_tmdb_recommendations(self, tmdb_id: int, page: int = 1) -> dict[str, Any] | None:
        return await self._get(f"/movie/{tmdb_id}/recommendations", {"page": page})

    # --- Batch Fetch for ML Cache ---

    async def get_movies_batch(self, list_type: str = "popular", pages: int = 5) -> list[dict]:
        """Fetch multiple pages of movies for ML cache building."""
        all_movies = []
        for page in range(1, pages + 1):
            if list_type == "popular":
                data = await self.get_popular(page)
            elif list_type == "top_rated":
                data = await self.get_top_rated(page)
            elif list_type == "trending":
                data = await self.get_trending(page)
            else:
                data = await self.get_popular(page)

            if data and "results" in data:
                all_movies.extend(data["results"])
            else:
                logger.warning(f"Failed to fetch {list_type} page {page}")
                break

        return all_movies


# Singleton instance
tmdb_client = TMDBClient()
