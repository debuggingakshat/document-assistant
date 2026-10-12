"""Reciprocal Rank Fusion (RRF) for combining vector and keyword retrieval results."""

import logging
import uuid
from collections.abc import Sequence

from app.retrieval.models import FusedChunk, RetrievedChunk

logger = logging.getLogger(__name__)

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion(
    semantic_results: Sequence[RetrievedChunk],
    keyword_results: Sequence[RetrievedChunk],
    k: int = DEFAULT_RRF_K,
    top_n: int = 10,
) -> list[FusedChunk]:
    """Combine and rank candidate chunks using Reciprocal Rank Fusion.

    RRF score for document d is calculated as:
        RRF(d) = SUM_{m in {semantic, keyword}} 1 / (k + rank_m(d))
    where rank_m(d) is 1-indexed.

    Args:
        semantic_results: Candidate chunks from vector search (sorted best-first).
        keyword_results: Candidate chunks from full-text search (sorted best-first).
        k: Smoothing constant (default 60, standard in IR literature).
        top_n: Number of fused results to return.

    Returns:
        List of FusedChunk objects sorted by descending rrf_score.
    """
    scores: dict[uuid.UUID, float] = {}
    sem_ranks: dict[uuid.UUID, int] = {}
    kw_ranks: dict[uuid.UUID, int] = {}
    chunk_map: dict[uuid.UUID, RetrievedChunk] = {}

    for rank, item in enumerate(semantic_results, start=1):
        scores[item.id] = scores.get(item.id, 0.0) + (1.0 / (k + rank))
        sem_ranks[item.id] = rank
        chunk_map[item.id] = item

    for rank, item in enumerate(keyword_results, start=1):
        scores[item.id] = scores.get(item.id, 0.0) + (1.0 / (k + rank))
        kw_ranks[item.id] = rank
        if item.id not in chunk_map:
            chunk_map[item.id] = item

    fused: list[FusedChunk] = []
    for chunk_id, rrf_score in scores.items():
        base_chunk = chunk_map[chunk_id]
        s_rank = sem_ranks.get(chunk_id)
        k_rank = kw_ranks.get(chunk_id)

        # If found by both, mark search_type as hybrid
        if s_rank is not None and k_rank is not None:
            chunk_copy = base_chunk.model_copy(update={"search_type": "hybrid"})
        else:
            chunk_copy = base_chunk

        fused.append(
            FusedChunk(
                chunk=chunk_copy,
                rrf_score=rrf_score,
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
