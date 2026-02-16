import logging

from app.config import settings

logger = logging.getLogger(__name__)

_model = None


def _load_model():
    global _model
    if _model is not None:
        return _model

    logger.info("Loading embedding model: %s (first call only)...", settings.embedding_model)
    from sentence_transformers import SentenceTransformer

    _model = SentenceTransformer(settings.embedding_model)
    logger.info("Embedding model loaded.")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts using bge-m3.

    Returns a list of float vectors (1024-dim for bge-m3).
    """
    model = _load_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def embed_query(text: str) -> list[float]:
    """Generate a single embedding for a query string."""
    return embed_texts([text])[0]
