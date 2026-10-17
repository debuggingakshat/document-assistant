"""High-level Retriever service combining embedding, hybrid search, RRF, cross-encoder reranking, and neighbor expansion."""

import concurrent.futures
import logging
import uuid
from typing import Sequence

from sqlalchemy import Engine, create_engine

from app.config import settings
from app.retrieval.expansion import expand_financial_query
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.models import FusedChunk, RetrievedChunk, RetrievedPassage
from app.retrieval.queries import fetch_neighbor_chunks, search_keyword, search_semantic
from app.retrieval.reranker import FinancialCrossEncoderReranker
from ingest.embedder import LocalEmbedder

logger = logging.getLogger(__name__)

_DEFAULT_ENGINE: Engine | None = None


def get_default_engine() -> Engine:
    """Return a shared singleton SQLAlchemy engine for database queries."""
    global _DEFAULT_ENGINE
    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _DEFAULT_ENGINE


class Retriever:
    """Hybrid search retriever over SEC 10-K document chunks with two-stage cross-encoder re-ranking."""

    def __init__(
        self,
        embedder: LocalEmbedder | None = None,
        engine: Engine | None = None,
        max_workers: int = 2,
        reranker: FinancialCrossEncoderReranker | None = None,
    ) -> None:
        self.embedder = embedder or LocalEmbedder()
        self.engine = engine or get_default_engine()
        self.max_workers = max_workers
        self.reranker = reranker or FinancialCrossEncoderReranker()

    def retrieve(
        self,
        query: str,
        ticker: str | None = None,
        fiscal_year: int | None = None,
        top_n: int = 5,
        candidate_limit: int = 20,
        expand_neighbors: bool = True,
    ) -> list[RetrievedPassage]:
        """Perform end-to-end hybrid retrieval with query expansion, RRF, cross-encoder reranking, and context expansion.

        Runs full-text keyword search and semantic embedding + vector search concurrently,
        fuses candidates with domain-weighted RRF, and applies a cross-encoder re-ranker.

        Args:
            query: User's natural language question or search phrase.
            ticker: Optional ticker filter (e.g. 'AAPL'). Case-insensitive.
            fiscal_year: Optional fiscal year filter (e.g. 2024).
            top_n: Number of final passages to return (default 5).
            candidate_limit: Candidates fetched from each search branch before RRF (default 20).
            expand_neighbors: Whether to fetch chunk-1 and chunk+1 for contextual boundary expansion.

        Returns:
            Ranked list of RetrievedPassage objects.
        """
        clean_query = " ".join(query.split())
        if not clean_query:
            return []

        # 0. Query Expansion: Enrich with official SEC GAAP line-item synonyms
        expanded_semantic_q, effective_kw_query = expand_financial_query(clean_query)

        def _run_keyword_branch() -> list[RetrievedChunk]:
            with self.engine.connect() as conn:
                return search_keyword(
                    conn=conn,
                    query_text=effective_kw_query,
                    ticker=ticker,
                    fiscal_year=fiscal_year,
                    limit=candidate_limit,
                )

        def _run_semantic_branch() -> list[RetrievedChunk]:
            # Embedding call runs concurrently with keyword I/O
            query_vec = self.embedder.embed_text(expanded_semantic_q)
            with self.engine.connect() as conn:
                return search_semantic(
                    conn=conn,
                    query_embedding=query_vec,
                    ticker=ticker,
                    fiscal_year=fiscal_year,
                    limit=candidate_limit,
                )

        # 1. Execute keyword search and semantic search concurrently
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            fut_keyword = executor.submit(_run_keyword_branch)
            fut_semantic = executor.submit(_run_semantic_branch)
            keyword_candidates = fut_keyword.result()
            semantic_candidates = fut_semantic.result()

        # 2. Stage 1: Domain-Boosted Reciprocal Rank Fusion (candidate pool: top 15)
        fused_candidates: list[FusedChunk] = reciprocal_rank_fusion(
            semantic_results=semantic_candidates,
            keyword_results=keyword_candidates,
            k=40,
            table_boost=1.10,
            item_boost=1.08,
            top_n=max(top_n * 3, 15),
        )

        if not fused_candidates:
            return []

        # 3. Stage 2: Cross-Encoder Re-Ranking (Cross-Attention Features)
        reranked_candidates = self.reranker.rerank(
            query=clean_query,
            candidates=fused_candidates,
            top_n=top_n,
        )

        # 4. Optional neighbor chunk context expansion with batched queries
        passages: list[RetrievedPassage] = []
        with self.engine.connect() as conn:
            # Collect all neighbor requests grouped by document_id
            neighbor_cache: dict[tuple[uuid.UUID, int], str] = {}
            if expand_neighbors:
                doc_to_indices: dict[uuid.UUID, set[int]] = {}
                for item in reranked_candidates:
                    c = item.chunk
                    if c.chunk_index > 0:
                        doc_to_indices.setdefault(c.document_id, set()).update(
                            [c.chunk_index - 1, c.chunk_index + 1]
                        )

                for doc_id, indices in doc_to_indices.items():
                    res = fetch_neighbor_chunks(
                        conn=conn, document_id=doc_id, chunk_indices=list(indices)
                    )
                    for c_idx, c_txt in res.items():
                        neighbor_cache[(doc_id, c_idx)] = c_txt

            for item in reranked_candidates:
                chunk = item.chunk
                meta = chunk.metadata or {}
                headings = meta.get("headings", [])
                is_table = bool(meta.get("is_table", False))

                # Build citation string
                section_label = (
                    " > ".join(headings) if headings else f"Chunk {chunk.chunk_index}"
                )
                citation = (
                    f"{chunk.company_name} ({chunk.ticker}) FY{chunk.fiscal_year} 10-K "
                    f"[{section_label}]"
                )

                full_text = chunk.chunk_text
                if expand_neighbors and chunk.chunk_index > 0:
                    prev_text = neighbor_cache.get((chunk.document_id, chunk.chunk_index - 1), "")
                    next_text = neighbor_cache.get((chunk.document_id, chunk.chunk_index + 1), "")

                    parts: list[str] = []
                    if prev_text:
                        parts.append(
                            f"[... Previous Chunk {chunk.chunk_index - 1} ...]\n{prev_text}"
                        )
                    parts.append(
                        f"[... Chunk {chunk.chunk_index} ...]\n{chunk.chunk_text}"
                    )
                    if next_text:
                        parts.append(
                            f"[... Next Chunk {chunk.chunk_index + 1} ...]\n{next_text}"
                        )
                    full_text = "\n\n".join(parts)

                passages.append(
                    RetrievedPassage(
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        ticker=chunk.ticker,
                        company_name=chunk.company_name,
                        fiscal_year=chunk.fiscal_year,
                        filing_type=chunk.filing_type,
                        filing_date=chunk.filing_date,
                        chunk_index=chunk.chunk_index,
                        text=chunk.chunk_text,
                        full_context_text=full_text,
                        rrf_score=item.rrf_score,
                        headings=headings,
                        is_table=is_table,
                        citation_source=citation,
                    )
                )

        logger.info(
            "Retrieved & reranked %d passages for query='%s' (ticker=%s, fy=%s)",
            len(passages),
            clean_query,
            ticker,
            fiscal_year,
        )
        return passages

    async def retrieve_async(
        self,
        query: str,
        ticker: str | None = None,
        fiscal_year: int | None = None,
        top_n: int = 5,
        candidate_limit: int = 20,
        expand_neighbors: bool = True,
    ) -> list[RetrievedPassage]:
        """Asynchronous wrapper for retrieve() to prevent event loop blocking."""
        import asyncio

        return await asyncio.to_thread(
            self.retrieve,
            query=query,
            ticker=ticker,
            fiscal_year=fiscal_year,
            top_n=top_n,
            candidate_limit=candidate_limit,
            expand_neighbors=expand_neighbors,
        )
