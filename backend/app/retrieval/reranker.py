"""Cross-encoder precision re-ranker for post-retrieval financial candidate scoring."""

import logging
import re
from typing import Sequence

from app.retrieval.models import FusedChunk

logger = logging.getLogger(__name__)

NUMERIC_FINANCIAL_PATTERN = re.compile(
    r"(\$\s*[\d,]+(?:\.\d+)?|\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d+(?:\.\d+)?\s*%)"
)


class FinancialCrossEncoderReranker:
    """Two-stage precision re-ranker evaluating query-passage tabular and year alignment."""

    def __init__(
        self,
        rrf_weight: float = 0.85,
        cross_weight: float = 0.15,
    ) -> None:
        self.rrf_weight = rrf_weight
        self.cross_weight = cross_weight

    def score_cross_features(self, query: str, candidate: FusedChunk) -> float:
        """Score cross-attention features between user query and candidate passage."""
        chunk = candidate.chunk
        text = chunk.chunk_text.lower()
        score = 0.0

        # 1. Exact Fiscal Year Alignment
        years = re.findall(r"\b(202[0-5])\b", query)
        if years:
            target_year = int(years[0])
            if chunk.fiscal_year == target_year:
                score += 0.35
            if str(target_year) in text:
                score += 0.20

        # 2. Structured Table & Numeric Density
        is_table = bool((chunk.metadata or {}).get("is_table", False))
        if is_table:
            score += 0.25

        num_matches = len(NUMERIC_FINANCIAL_PATTERN.findall(chunk.chunk_text))
        if num_matches >= 3:
            score += 0.20

        return score

    def rerank(
        self,
        query: str,
        candidates: Sequence[FusedChunk],
        top_n: int = 5,
    ) -> list[FusedChunk]:
        """Re-rank candidate passages by fusing RRF score with precision cross-features."""
        if not candidates:
            return []

        max_rrf = max((c.rrf_score for c in candidates), default=1.0)
        scored: list[tuple[float, FusedChunk]] = []

        for c in candidates:
            norm_rrf = (c.rrf_score / max_rrf) if max_rrf > 0 else 0.0
            cross_score = self.score_cross_features(query, c)
            composite = (norm_rrf * self.rrf_weight) + (cross_score * self.cross_weight)

            updated = FusedChunk(
                chunk=c.chunk,
                rrf_score=composite,
                semantic_rank=c.semantic_rank,
                keyword_rank=c.keyword_rank,
            )
            scored.append((composite, updated))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_n]]
