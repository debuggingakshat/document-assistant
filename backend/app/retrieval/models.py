"""Data models for retrieved and fused passages."""

import uuid
from typing import Any

from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    """A single chunk returned from either vector or keyword search."""

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    chunk_text: str
    token_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    ticker: str
    company_name: str
    fiscal_year: int
    filing_type: str
    filing_date: str
    score: float = 0.0
    search_type: str = "unknown"  # 'semantic' or 'keyword'


class FusedChunk(BaseModel):
    """A chunk that has been ranked via Reciprocal Rank Fusion."""

    chunk: RetrievedChunk
    rrf_score: float
    semantic_rank: int | None = None
    keyword_rank: int | None = None


class RetrievedPassage(BaseModel):
    """A final retrieval result with optional surrounding neighbor context."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    ticker: str
    company_name: str
    fiscal_year: int
    filing_type: str
    filing_date: str
    chunk_index: int
    text: str
    full_context_text: str
    rrf_score: float
    headings: list[str] = Field(default_factory=list)
    is_table: bool = False
    citation_source: str = ""
