"""Reciprocal Rank Fusion (RRF) with financial table and Item 7/8 section boosting."""

import logging
import uuid
from collections.abc import Sequence

from app.retrieval.models import FusedChunk, RetrievedChunk

logger = logging.getLogger(__name__)

DEFAULT_RRF_K = 40  # Calibrated for dense corporate filing retrieval


def reciprocal_rank_fusion(
    semantic_results: Sequence[RetrievedChunk],
    keyword_results: Sequence[RetrievedChunk],
    k: int = DEFAULT_RRF_K,
    semantic_weight: float = 1.0,
    keyword_weight: float = 1.0,
    table_boost: float = 1.10,
    item_boost: float = 1.08,
    top_n: int = 10,
) -> list[FusedChunk]:
    """Combine and rank candidate chunks using Reciprocal Rank Fusion with domain boosts.

    RRF score for document d is calculated as:
        RRF(d) = [ w_sem / (k + rank_sem(d)) + w_kw / (k + rank_kw(d)) ] * boost(d)
    where rank_m(d) is 1-indexed, and boost(d) rewards structured financial tables (Item 7/8).

    Args:
        semantic_results: Candidate chunks from vector search (sorted best-first).
        keyword_results: Candidate chunks from full-text search (sorted best-first).
        k: Smoothing constant (default 40, calibrated for high financial precision).
        semantic_weight: Weight applied to semantic vector ranks (default 1.0).
        keyword_weight: Weight applied to keyword FTS ranks (default 1.0).
        table_boost: Score multiplier for chunks containing structured financial tables (default 1.10).
        item_boost: Score multiplier for chunks from Item 7 (MD&A) and Item 8 (Financial Statements) (default 1.08).
        top_n: Number of fused results to return.

    Returns:
        List of FusedChunk objects sorted by descending boosted rrf_score.
    """
    scores: dict[uuid.UUID, float] = {}
    sem_ranks: dict[uuid.UUID, int] = {}
    kw_ranks: dict[uuid.UUID, int] = {}
    chunk_map: dict[uuid.UUID, RetrievedChunk] = {}

    for rank, item in enumerate(semantic_results, start=1):
        scores[item.id] = scores.get(item.id, 0.0) + (semantic_weight / (k + rank))
        sem_ranks[item.id] = rank
        chunk_map[item.id] = item

    for rank, item in enumerate(keyword_results, start=1):
        scores[item.id] = scores.get(item.id, 0.0) + (keyword_weight / (k + rank))
        kw_ranks[item.id] = rank
        if item.id not in chunk_map:
            chunk_map[item.id] = item

    fused: list[FusedChunk] = []
    for chunk_id, raw_rrf_score in scores.items():
        base_chunk = chunk_map[chunk_id]
        s_rank = sem_ranks.get(chunk_id)
        k_rank = kw_ranks.get(chunk_id)

        # Apply domain boosts for financial tables and Item 7/8 disclosures
        meta = base_chunk.metadata or {}
        is_table = bool(meta.get("is_table", False))
        headings = [str(h).lower() for h in meta.get("headings", [])]
        is_primary_section = any(
            "item 7" in h or "item 8" in h or "financial statements" in h or "results of operations" in h
            for h in headings
        )

        multiplier = 1.0
        if is_table:
            multiplier *= table_boost
        if is_primary_section:
            multiplier *= item_boost

        final_score = raw_rrf_score * multiplier

        # If found by both, mark search_type as hybrid
        if s_rank is not None and k_rank is not None:
            chunk_copy = base_chunk.model_copy(update={"search_type": "hybrid"})
        else:
            chunk_copy = base_chunk

        fused.append(
            FusedChunk(
                chunk=chunk_copy,
                rrf_score=final_score,
                semantic_rank=s_rank,
                keyword_rank=k_rank,
            )
        )

    # Sort descending by rrf_score, breaking ties by lowest semantic rank, then keyword rank
    fused.sort(
        key=lambda fc: (
            fc.rrf_score,
            -(fc.semantic_rank if fc.semantic_rank is not None else 999999),
            -(fc.keyword_rank if fc.keyword_rank is not None else 999999),
        ),
        reverse=True,
    )

    logger.debug(
        "RRF fused %d semantic + %d keyword candidates into %d unique items; returning top %d",
        len(semantic_results),
        len(keyword_results),
        len(fused),
        min(top_n, len(fused)),
    )

    return fused[:top_n]
