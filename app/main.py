import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.services.tmdb_client import tmdb_client
from app.routers import auth, movies, lists, ratings, recommendations, system
from ml.recommender import get_recommender

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting CineMatch API ({settings.ENVIRONMENT})")
    logger.info("TMDB client initialized")

    # Load ML model from disk if available
    recommender = get_recommender()
    if recommender.load_from_disk():
        logger.info(f"ML model loaded: {len(recommender.movie_ids)} movies in matrix")
    else:
        logger.info("No ML model found — recommendations will use TMDB fallback")

    yield
    # Shutdown
    await tmdb_client.close()
    logger.info("CineMatch API shutdown complete")


app = FastAPI(
    title="CineMatch API",
    description="AI-powered movie recommendation engine",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(movies.router)
app.include_router(lists.router)
app.include_router(ratings.router)
app.include_router(recommendations.router)
app.include_router(system.router)
