import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.services.cache_service import get_all_cached_movies
from app.utils.dependencies import get_db
from ml.recommender import get_recommender
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/debug/ml-status")
async def ml_status():
    recommender = get_recommender()
    return {
        "matrix_loaded": recommender.is_ready,
        "movie_count": len(recommender.movie_ids),
        "matrix_shape": list(recommender.matrix.shape) if recommender.matrix is not None else None,
    }


@router.post("/system/rebuild-matrix")
async def rebuild_matrix(db: AsyncSession = Depends(get_db)):
    """Rebuild ML matrix from all cached movies."""
    movies = await get_all_cached_movies(db)
    recommender = get_recommender()
    result = recommender.build_matrix(movies)

    logger.info(f"Matrix rebuild: {result}")
    return result
