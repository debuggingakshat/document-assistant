"""Local BGE 768-dimensional sentence-transformers embedder."""

import logging
from typing import Sequence

import torch
from sentence_transformers import SentenceTransformer
from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "BAAI/bge-base-en-v1.5"
EXPECTED_DIMENSIONS = 768


class LocalEmbedder:
    """Generates 768-dimensional vector embeddings locally on device."""

    def __init__(
        self,
        model_name: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        self.model_name = model_name or settings.embedding_model or DEFAULT_MODEL_NAME
        self.dimensions = dimensions or settings.embedding_dimensions or EXPECTED_DIMENSIONS

        # Detect optimal device on this machine (Metal/MPS on Apple Silicon, else CPU)
        if torch.backends.mps.is_available():
            self.device = "mps"
        elif torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"

        logger.info(
            "Loading local embedding model '%s' on device '%s'...",
            self.model_name,
            self.device,
        )
        self.model = SentenceTransformer(self.model_name, device=self.device)

    def embed_text(self, text: str) -> list[float]:
        """Generate normalized embedding for a single text."""
        result = self.embed_batch([text])
        return result[0]

    def embed_batch(
        self,
        texts: Sequence[str],
        batch_size: int = 64,
    ) -> list[list[float]]:
        """Generate normalized embeddings for a batch of texts."""
        if not texts:
            return []

        clean_texts = [" ".join(t.split()) for t in texts]
        embeddings = self.model.encode(
            clean_texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vec.tolist() for vec in embeddings]


# Alias for compatibility
DocumentEmbedder = LocalEmbedder
OpenAIEmbedder = LocalEmbedder
