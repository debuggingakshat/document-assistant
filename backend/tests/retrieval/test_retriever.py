"""Unit tests for Retriever class using mocks."""

import uuid
from unittest.mock import MagicMock, patch

from app.retrieval.models import RetrievedChunk
from app.retrieval.retriever import Retriever


class MockEmbedder:
    """Mock embedder returning fixed 768-dim vector without loading ML models."""

    def embed_text(self, text: str) -> list[float]:
        return [0.01] * 768


def _sample_chunk(
    doc_id: uuid.UUID,
    chunk_index: int = 5,
    headings: list[str] | None = None,
    is_table: bool = False,
) -> RetrievedChunk:
    return RetrievedChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        chunk_index=chunk_index,
        chunk_text=f"Content for chunk {chunk_index}.",
        token_count=20,
        metadata={
            "headings": headings or ["Item 7. MD&A", "Results of Operations"],
            "is_table": is_table,
        },
        ticker="AAPL",
        company_name="Apple Inc.",
        fiscal_year=2024,
        filing_type="10-K",
        filing_date="2024-11-01",
        score=0.9,
        search_type="semantic",
    )


def test_retriever_empty_query() -> None:
    """Empty query string returns empty result without hitting DB."""
    retriever = Retriever(embedder=MockEmbedder(), engine=MagicMock())
    assert retriever.retrieve("") == []
    assert retriever.retrieve("   ") == []


@patch("app.retrieval.retriever.fetch_neighbor_chunks")
@patch("app.retrieval.retriever.search_keyword")
@patch("app.retrieval.retriever.search_semantic")
def test_retriever_end_to_end_flow(
    mock_search_sem: MagicMock,
    mock_search_kw: MagicMock,
    mock_fetch_neighbors: MagicMock,
) -> None:
    """Retriever properly orchestrates embedding, DB searches, RRF, and neighbor expansion."""
    doc_id = uuid.uuid4()
    candidate = _sample_chunk(doc_id=doc_id, chunk_index=5, is_table=True)

    mock_search_sem.return_value = [candidate]
    mock_search_kw.return_value = [candidate]
    mock_fetch_neighbors.return_value = {
        4: "Preceding context about sales.",
        6: "Succeeding context about operating income.",
    }

    mock_engine = MagicMock()
    # mock context manager for engine.connect()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    retriever = Retriever(embedder=MockEmbedder(), engine=mock_engine)
    results = retriever.retrieve(
        query="Apple revenue 2024",
        ticker="AAPL",
        fiscal_year=2024,
        top_n=1,
        expand_neighbors=True,
    )

    assert len(results) == 1
    p = results[0]
    assert p.ticker == "AAPL"
    assert p.fiscal_year == 2024
    assert p.is_table is True
    assert "Item 7. MD&A" in p.headings
    assert "Apple Inc. (AAPL) FY2024 10-K" in p.citation_source

    # Check neighbor expansion included in full_context_text
    assert "Preceding context about sales." in p.full_context_text
    assert "Content for chunk 5." in p.full_context_text
    assert "Succeeding context about operating income." in p.full_context_text


@patch("app.retrieval.retriever.fetch_neighbor_chunks")
@patch("app.retrieval.retriever.search_keyword")
@patch("app.retrieval.retriever.search_semantic")
def test_retriever_without_neighbor_expansion(
    mock_search_sem: MagicMock,
    mock_search_kw: MagicMock,
    mock_fetch_neighbors: MagicMock,
) -> None:
    """When expand_neighbors=False, neighbor queries are skipped."""
    doc_id = uuid.uuid4()
    candidate = _sample_chunk(doc_id=doc_id, chunk_index=5)

    mock_search_sem.return_value = [candidate]
    mock_search_kw.return_value = []

    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    retriever = Retriever(embedder=MockEmbedder(), engine=mock_engine)
    results = retriever.retrieve(
        query="Apple revenue",
        expand_neighbors=False,
    )

    assert len(results) == 1
    p = results[0]
    assert p.full_context_text == candidate.chunk_text
    mock_fetch_neighbors.assert_not_called()
