import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent / "data" / "model.pkl"


class MovieRecommender:
    def __init__(self):
        self.tfidf = TfidfVectorizer(
            max_features=5000,
            stop_words="english",
            ngram_range=(1, 2),
        )
        self.matrix = None
        self.movie_ids: list[int] = []
        self.is_ready = False

    def build_matrix(self, movies: list[dict]) -> dict:
        """Build TF-IDF matrix from cached movies.

        Each movie dict should have: tmdb_id, overview, genres (list[str]),
        keywords (list[str]), tagline.
        """
        if len(movies) < 10:
            self.is_ready = False
            return {
                "status": "insufficient_data",
                "movie_count": len(movies),
                "minimum_required": 10,
            }

        self.movie_ids = [m["tmdb_id"] for m in movies]

        text_blobs = []
        for m in movies:
            genres = " ".join(m.get("genres", []))
            keywords = " ".join(m.get("keywords", []))
            blob = f"{m.get('overview', '')} {genres} {keywords} {m.get('tagline', '')}"
            text_blobs.append(blob)

        self.matrix = self.tfidf.fit_transform(text_blobs)
        self.is_ready = True

        # Persist to disk
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "matrix": self.matrix,
                "movie_ids": self.movie_ids,
                "tfidf": self.tfidf,
            },
            MODEL_PATH,
        )
        logger.info(f"ML matrix built: {len(movies)} movies, shape {self.matrix.shape}")

        return {
            "status": "rebuilt",
            "movie_count": len(movies),
            "matrix_shape": list(self.matrix.shape),
        }

    def get_similar(self, tmdb_id: int, top_n: int = 15) -> list[int]:
        """Return top_n similar tmdb_ids by content similarity."""
        if not self.is_ready or tmdb_id not in self.movie_ids:
            return []

        idx = self.movie_ids.index(tmdb_id)
        sim_scores = cosine_similarity(self.matrix[idx], self.matrix).flatten()
        # Exclude self
        sim_scores[idx] = -1
        similar_indices = sim_scores.argsort()[-top_n:][::-1]
        return [self.movie_ids[i] for i in similar_indices if sim_scores[i] > 0]

    def get_personalized(self, user_ratings: dict[int, float], top_n: int = 20) -> list[int]:
        """Build a user taste profile from ratings and find closest unseen movies.

        user_ratings: {tmdb_id: rating_score (0.5-5.0)}
        """
        if not self.is_ready or not user_ratings:
            return []

        rated_indices = []
        weights = []
        for tmdb_id, rating in user_ratings.items():
            if tmdb_id in self.movie_ids:
                idx = self.movie_ids.index(tmdb_id)
                rated_indices.append(idx)
                weights.append(rating)

        if not rated_indices:
            return []

        # Weighted average of rated movie vectors → user profile
        weight_array = np.array(weights)
        rated_vectors = self.matrix[rated_indices].toarray()
        user_profile = np.average(rated_vectors, axis=0, weights=weight_array).reshape(1, -1)

        sim_scores = cosine_similarity(user_profile, self.matrix).flatten()

        # Exclude already-rated movies
        for idx in rated_indices:
            sim_scores[idx] = -1

        top_indices = sim_scores.argsort()[-top_n:][::-1]
        return [self.movie_ids[i] for i in top_indices if sim_scores[i] > 0]

    def load_from_disk(self) -> bool:
        """Load pre-built model on startup."""
        try:
            data = joblib.load(MODEL_PATH)
            self.matrix = data["matrix"]
            self.movie_ids = data["movie_ids"]
            self.tfidf = data["tfidf"]
            self.is_ready = True
            logger.info(f"ML model loaded from disk: {len(self.movie_ids)} movies")
            return True
        except FileNotFoundError:
            logger.info("No ML model found on disk — will use TMDB fallback")
            self.is_ready = False
            return False


# Global singleton
_recommender: MovieRecommender | None = None


def get_recommender() -> MovieRecommender:
    global _recommender
    if _recommender is None:
        _recommender = MovieRecommender()
    return _recommender
