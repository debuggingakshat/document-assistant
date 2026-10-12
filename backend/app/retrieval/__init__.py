"""Retrieval package for Document Assistant."""

from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.models import FusedChunk, RetrievedChunk, RetrievedPassage
from app.retrieval.queries import fetch_neighbor_chunks, search_keyword, search_semantic
from app.retrieval.retriever import Retriever

__all__ = [
    "FusedChunk",
    "RetrievedChunk",
    "RetrievedPassage",
    "Retriever",
    "fetch_neighbor_chunks",
    "reciprocal_rank_fusion",
    "search_keyword",
    "search_semantic",
]
