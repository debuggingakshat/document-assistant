"""Unit tests for the two-stage financial cross-encoder reranker."""

import uuid
from app.retrieval.models import FusedChunk, RetrievedChunk
from app.retrieval.reranker import FinancialCrossEncoderReranker


def _make_fused_chunk(
    text: str,
    fiscal_year: int = 2024,
    is_table: bool = False,
    headings: list[str] | None = None,
    rrf_score: float = 0.03,
) -> FusedChunk:
    chunk = RetrievedChunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=1,
        chunk_text=text,
        token_count=20,
        metadata={"is_table": is_table, "headings": headings or []},
        ticker="AAPL",
        company_name="Apple Inc.",
        fiscal_year=fiscal_year,
        filing_type="10-K",
        filing_date="2024-11-01",
        score=0.8,
        search_type="hybrid",
    )
    return FusedChunk(chunk=chunk, rrf_score=rrf_score)


def test_cross_encoder_prioritizes_exact_table_and_year() -> None:
    reranker = FinancialCrossEncoderReranker()

    # Candidate A: Narrative commentary mentioning 2023
    cand_a = _make_fused_chunk(
        text="The company considers macroeconomic factors during 2023.",
        fiscal_year=2023,
        is_table=False,
        rrf_score=0.032,
    )

    # Candidate B: Financial table with formatted rows for 2024
    cand_b = _make_fused_chunk(
        text="iPhone net sales: 2024 = $201,183 million; 2023 = $200,583 million.",
        fiscal_year=2024,
        is_table=True,
        headings=["Item 7. MD&A", "Results of Operations"],
        rrf_score=0.030,
    )

    query = "What were Apple's iPhone net sales in 2024?"
    reranked = reranker.rerank(query, [cand_a, cand_b], top_n=2)

    # Candidate B should leapfrog Candidate A because of exact year, table structure, and financial figures
    assert len(reranked) == 2
    assert reranked[0].chunk.id == cand_b.chunk.id
    assert reranked[0].chunk.fiscal_year == 2024
