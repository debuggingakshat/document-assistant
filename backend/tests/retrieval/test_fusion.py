"""Unit tests for Reciprocal Rank Fusion (RRF)."""

import uuid

import pytest

from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.models import RetrievedChunk


def _make_chunk(
    chunk_id: uuid.UUID | None = None,
    chunk_index: int = 0,
    text: str = "Test chunk text",
    search_type: str = "semantic",
    score: float = 0.8,
) -> RetrievedChunk:
    """Helper to instantiate test RetrievedChunk."""
    return RetrievedChunk(
        id=chunk_id or uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=chunk_index,
        chunk_text=text,
        token_count=10,
        metadata={},
        ticker="AAPL",
        company_name="Apple Inc.",
        fiscal_year=2024,
        filing_type="10-K",
        filing_date="2024-11-01",
        score=score,
        search_type=search_type,
    )


def test_rrf_empty_inputs() -> None:
    """RRF with empty lists should return empty list."""
    assert reciprocal_rank_fusion([], []) == []


def test_rrf_single_source_ranking() -> None:
    """RRF with only semantic results should preserve order with 1/(k+rank) formula."""
    c1 = _make_chunk(chunk_index=1)
    c2 = _make_chunk(chunk_index=2)
    k = 60

    fused = reciprocal_rank_fusion([c1, c2], [], k=k, top_n=10)
    assert len(fused) == 2
    assert fused[0].chunk.id == c1.id
    assert fused[1].chunk.id == c2.id

    assert pytest.approx(fused[0].rrf_score, 1e-6) == 1.0 / (k + 1)
    assert pytest.approx(fused[1].rrf_score, 1e-6) == 1.0 / (k + 2)
    assert fused[0].semantic_rank == 1
    assert fused[0].keyword_rank is None


def test_rrf_both_sources_boost_mutual_chunk() -> None:
    """A chunk found in both searches should receive the sum of RRF scores and rank highest."""
    mutual_id = uuid.uuid4()
    sem_only_id = uuid.uuid4()
    kw_only_id = uuid.uuid4()

    c_mutual_sem = _make_chunk(
        chunk_id=mutual_id, text="Mutual passage", search_type="semantic"
    )
    c_sem_only = _make_chunk(
        chunk_id=sem_only_id, text="Semantic only", search_type="semantic"
    )

    c_kw_only = _make_chunk(
        chunk_id=kw_only_id, text="Keyword only", search_type="keyword"
    )
    c_mutual_kw = _make_chunk(
        chunk_id=mutual_id, text="Mutual passage", search_type="keyword"
    )

    # Order:
    # Semantic: [c_sem_only (rank 1), c_mutual_sem (rank 2)]
    # Keyword:  [c_mutual_kw (rank 1), c_kw_only (rank 2)]
    fused = reciprocal_rank_fusion(
        semantic_results=[c_sem_only, c_mutual_sem],
        keyword_results=[c_mutual_kw, c_kw_only],
        k=60,
        top_n=10,
    )

    assert len(fused) == 3
    # Mutual chunk has score = 1/(60+2) + 1/(60+1) ~= 0.016129 + 0.016393 = 0.03252
    # Sem only: 1/(60+1) ~= 0.016393
    # Kw only: 1/(60+2) ~= 0.016129
    assert fused[0].chunk.id == mutual_id
    assert fused[0].chunk.search_type == "hybrid"
    assert fused[0].semantic_rank == 2
    assert fused[0].keyword_rank == 1

    expected_score = (1.0 / 62) + (1.0 / 61)
    assert pytest.approx(fused[0].rrf_score, 1e-6) == expected_score


def test_rrf_top_n_truncation() -> None:
    """RRF should truncate results to top_n."""
    chunks = [_make_chunk(chunk_index=i) for i in range(15)]
    fused = reciprocal_rank_fusion(semantic_results=chunks, keyword_results=[], top_n=5)
    assert len(fused) == 5
