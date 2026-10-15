"""Google AI Studio 768-dimensional embedder with multi-key rotation and TPM pacing."""

import logging
import time
from typing import Sequence

from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "gemini-embedding-001"
EXPECTED_DIMENSIONS = 768


class GoogleEmbedder:
    """Generates 768-dimensional vector embeddings with automatic key rotation and TPM pacing."""

    def __init__(
        self,
        model_name: str | None = None,
        dimensions: int | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model_name = model_name or settings.embedding_model or DEFAULT_MODEL_NAME
        self.dimensions = dimensions or settings.embedding_dimensions or EXPECTED_DIMENSIONS

        raw_keys = api_key or settings.google_api_key or settings.gemini_api_key
        if not raw_keys:
            raise ValueError(
                "No Google API key found. Please set GOOGLE_API_KEY or GEMINI_API_KEY."
            )
        self.all_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        # List of active keys that have not hit daily quota
        self.active_keys = list(self.all_keys)
        self.current_idx = 0
        self.client = genai.Client(api_key=self.active_keys[0])
        self.config = types.EmbedContentConfig(output_dimensionality=self.dimensions)
        logger.info(
            "Initialized GoogleEmbedder with model '%s' (%d dimensions, %d active key(s))",
            self.model_name,
            self.dimensions,
            len(self.active_keys),
        )

    def _mark_key_exhausted_and_rotate(self) -> bool:
        """Permanently drop current key from daily pool and switch to next key."""
        if not self.active_keys:
            return False
        bad_key = self.active_keys.pop(self.current_idx)
        logger.error(
            "Google API key ending in ...%s has reached daily quota. Dropped from pool. %d key(s) remaining.",
            bad_key[-6:],
            len(self.active_keys),
        )
        if not self.active_keys:
            return False
        self.current_idx = self.current_idx % len(self.active_keys)
        self.client = genai.Client(api_key=self.active_keys[self.current_idx])
        return True

    def _rotate_to_next_active_key(self) -> None:
        """Round-robin to next active key."""
        if len(self.active_keys) > 1:
            self.current_idx = (self.current_idx + 1) % len(self.active_keys)
            self.client = genai.Client(api_key=self.active_keys[self.current_idx])

    def embed_text(self, text: str) -> list[float]:
        """Generate normalized 768-dim embedding for a single text."""
        result = self.embed_batch([text], batch_size=1, delay_between_batches=0.0)
        if not result:
            raise RuntimeError(f"Failed to generate embedding for text: {text[:50]}...")
        return result[0]

    def embed_batch(
        self,
        texts: Sequence[str],
        batch_size: int = 6,
        delay_between_batches: float = 2.5,
        max_retries: int = 8,
    ) -> list[list[float]]:
        """Generate embeddings with TPM pacing and robust retry."""
        if not texts:
            return []

        clean_texts = [" ".join(t.split()) for t in texts]
        all_embeddings: list[list[float]] = []
        effective_batch_size = min(batch_size, 6)

        for i in range(0, len(clean_texts), effective_batch_size):
            batch = clean_texts[i : i + effective_batch_size]
            embeddings = self._embed_chunk_with_retry(batch, max_retries=max_retries)
            all_embeddings.extend(embeddings)

            # Round-robin between active keys to distribute TPM load
            self._rotate_to_next_active_key()

            # Pacing delay to stay well below 30,000 TPM limit
            if i + effective_batch_size < len(clean_texts) and delay_between_batches > 0:
                time.sleep(delay_between_batches)

        return all_embeddings

    def _embed_chunk_with_retry(
        self,
        batch: list[str],
        max_retries: int = 8,
    ) -> list[list[float]]:
        """Embed a sub-batch of texts with exponential backoff on TPM limits and daily failover."""
        last_error = None
        for attempt in range(max_retries):
            if not self.active_keys:
                raise RuntimeError("All Google API keys in pool have exhausted their daily quota.")
            try:
                response = self.client.models.embed_content(
                    model=self.model_name,
                    contents=batch,
                    config=self.config,
                )
                if not response.embeddings:
                    raise RuntimeError("Google API returned empty embeddings list")

                return [emb.values for emb in response.embeddings]

            except (ClientError, APIError, Exception) as err:
                last_error = err
                err_str = str(err)

                # Check if it is a daily quota exhaustion
                is_daily_limit = "EmbedContentRequestsPerDay" in err_str or "Retry in 7h" in err_str or "retry in 7h" in err_str or "retryDelay" in err_str

                if is_daily_limit:
                    if self._mark_key_exhausted_and_rotate():
                        time.sleep(1.0)
                        continue
                    else:
                        raise RuntimeError(f"All API keys exhausted daily limit: {err_str}")

                # If it is a TPM / RPM rate limit (temporary), wait for sliding window to drain
                wait_seconds = 10 + (attempt * 5)
                logger.warning(
                    "Google embedding rate-limited (%d/%d): %s. Pausing for %ds...",
                    attempt + 1,
                    max_retries,
                    err_str[:80],
                    wait_seconds,
                )
                # Rotate key to spread TPM load
                self._rotate_to_next_active_key()
                time.sleep(wait_seconds)

        raise RuntimeError(
            f"Failed to embed batch of {len(batch)} texts after {max_retries} attempts: {last_error}"
        )


# Backward compatibility aliases
LocalEmbedder = GoogleEmbedder
DocumentEmbedder = GoogleEmbedder
OpenAIEmbedder = GoogleEmbedder
