"""Docling-based document chunking module with OpenAI tiktoken calibration."""

import hashlib
import logging
from pathlib import Path
from typing import Any

from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.base import BaseTokenizer
import tiktoken

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_MAX_TOKENS = 800


class OpenAITiktokenTokenizer(BaseTokenizer):
    """Tiktoken-backed tokenizer for Docling HybridChunker.

    Ensures exact token-length compliance with OpenAI text-embedding-3 models
    without requiring external HuggingFace downloads or mismatching token boundaries.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        super().__init__()
        try:
            self._encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            self._encoding = tiktoken.get_encoding("cl100k_base")
        self._max_tokens = max_tokens

    def get_tokenizer(self) -> Any:
        return self._encoding

    def get_max_tokens(self) -> int:
        return self._max_tokens

    def count_tokens(self, text: str) -> int:
        return len(self._encoding.encode(text))


class DocumentChunker:
    """Chunks normalized Markdown documents into semantic passages."""

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        self.max_tokens = max_tokens
        self.tokenizer = OpenAITiktokenTokenizer(
            model_name=model_name, max_tokens=max_tokens
        )
        self.chunker = HybridChunker(tokenizer=self.tokenizer)
        self.converter = DocumentConverter()

    def chunk_file(
        self,
        file_path: Path,
        doc_meta: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Chunk a Markdown filing and return a list of deduplicated chunk dictionaries.

        Each dictionary contains:
            - chunk_index: int
            - chunk_text: str
            - token_count: int
            - metadata: dict (headings, ticker, fiscal_year, is_table, etc.)
        """
        if not file_path.exists():
            msg = f"Markdown file not found: {file_path}"
            raise FileNotFoundError(msg)

        text_content = file_path.read_text(encoding="utf-8")
        if not text_content.strip():
            logger.warning("Empty file: %s", file_path)
            return []

        conv_res = self.converter.convert(file_path)
        docling_doc = conv_res.document
        raw_chunks = list(self.chunker.chunk(docling_doc))

        cleaned_chunks: list[dict[str, Any]] = []
        seen_hashes: set[str] = set()
        chunk_idx = 0

        base_meta = doc_meta or {}

        for raw_chunk in raw_chunks:
            chunk_text = raw_chunk.text.strip()
            if not chunk_text:
                continue

            # Check for duplicate chunks via content hash
            content_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
            if content_hash in seen_hashes:
                logger.debug("Skipping duplicate chunk in %s", file_path.name)
                continue
            seen_hashes.add(content_hash)

            # Accurate token count
            token_count = self.tokenizer.count_tokens(chunk_text)
            if token_count == 0:
                continue

            # Extract headings path
            headings: list[str] = []
            if raw_chunk.meta and getattr(raw_chunk.meta, "headings", None):
                headings = [h.strip() for h in raw_chunk.meta.headings if h and h.strip()]

            # Detect if chunk includes a table
            is_table = False
            if raw_chunk.meta and getattr(raw_chunk.meta, "doc_items", None):
                for item in raw_chunk.meta.doc_items:
                    label = str(getattr(item, "label", "")).lower()
                    if "table" in label:
                        is_table = True
                        break

            chunk_meta = {
                **base_meta,
                "headings": headings,
                "is_table": is_table,
                "file_name": file_path.name,
            }

            cleaned_chunks.append(
                {
                    "chunk_index": chunk_idx,
                    "chunk_text": chunk_text,
                    "token_count": token_count,
                    "metadata": chunk_meta,
                }
            )
            chunk_idx += 1

        logger.info(
            "Chunked %s into %d unique chunks (max tokens: %d)",
            file_path.name,
            len(cleaned_chunks),
            self.max_tokens,
        )
        return cleaned_chunks
