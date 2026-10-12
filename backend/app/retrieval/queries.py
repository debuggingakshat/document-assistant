"""Database query operations for semantic and full-text keyword retrieval."""

import logging
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Connection, text

from app.retrieval.models import RetrievedChunk

logger = logging.getLogger(__name__)


def search_semantic(
    conn: Connection,
    query_embedding: Sequence[float],
    ticker: str | None = None,
    fiscal_year: int | None = None,
    limit: int = 20,
) -> list[RetrievedChunk]:
    """Execute pgvector cosine distance search over document_chunks."""
    where_clauses: list[str] = []
    params: dict[str, Any] = {
        "query_vec": str(list(query_embedding)),
        "limit": limit,
    }

    if ticker:
        where_clauses.append("sd.ticker = :ticker")
        params["ticker"] = ticker.upper()
    if fiscal_year is not None:
        where_clauses.append("sd.fiscal_year = :fiscal_year")
        params["fiscal_year"] = fiscal_year

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    sql_str = f"""
        SELECT 
            dc.id,
            dc.document_id,
            dc.chunk_index,
            dc.chunk_text,
            dc.token_count,
            dc.metadata,
            sd.ticker,
            sd.company_name,
            sd.fiscal_year,
            sd.filing_type,
            sd.filing_date,
            (dc.embedding <=> CAST(:query_vec AS vector)) AS distance
        FROM document_chunks dc
        JOIN source_documents sd ON dc.document_id = sd.id
        {where_sql}
        ORDER BY dc.embedding <=> CAST(:query_vec AS vector) ASC
        LIMIT :limit;
    """

    rows = conn.execute(text(sql_str), params).mappings().fetchall()
    results: list[RetrievedChunk] = []

    for row in rows:
        dist = float(row["distance"])
        sim_score = max(0.0, 1.0 - dist)
        results.append(
            RetrievedChunk(
                id=row["id"],
                document_id=row["document_id"],
                chunk_index=row["chunk_index"],
                chunk_text=row["chunk_text"],
                token_count=row["token_count"],
                metadata=row["metadata"] or {},
                ticker=row["ticker"],
                company_name=row["company_name"],
                fiscal_year=row["fiscal_year"],
                filing_type=row["filing_type"],
                filing_date=row["filing_date"],
                score=sim_score,
                search_type="semantic",
            )
        )

    logger.debug("Semantic search returned %d candidates", len(results))
    return results


def search_keyword(
    conn: Connection,
    query_text: str,
    ticker: str | None = None,
    fiscal_year: int | None = None,
    limit: int = 20,
) -> list[RetrievedChunk]:
    """Execute Postgres full-text search over document_chunks.search_vector."""
    clean_query = " ".join(query_text.split())
    if not clean_query:
        return []

    where_clauses: list[str] = [
        "dc.search_vector @@ websearch_to_tsquery('english', :query_text)"
    ]
    params: dict[str, Any] = {
        "query_text": clean_query,
        "limit": limit,
    }

    if ticker:
        where_clauses.append("sd.ticker = :ticker")
        params["ticker"] = ticker.upper()
    if fiscal_year is not None:
        where_clauses.append("sd.fiscal_year = :fiscal_year")
        params["fiscal_year"] = fiscal_year

    where_sql = f"WHERE {' AND '.join(where_clauses)}"

    sql_str = f"""
        SELECT 
            dc.id,
            dc.document_id,
            dc.chunk_index,
            dc.chunk_text,
            dc.token_count,
            dc.metadata,
            sd.ticker,
            sd.company_name,
            sd.fiscal_year,
            sd.filing_type,
            sd.filing_date,
            ts_rank_cd(dc.search_vector, websearch_to_tsquery('english', :query_text)) AS rank
        FROM document_chunks dc
        JOIN source_documents sd ON dc.document_id = sd.id
        {where_sql}
        ORDER BY rank DESC
        LIMIT :limit;
    """

    rows = conn.execute(text(sql_str), params).mappings().fetchall()
    results: list[RetrievedChunk] = []

    for row in rows:
        results.append(
            RetrievedChunk(
                id=row["id"],
                document_id=row["document_id"],
                chunk_index=row["chunk_index"],
                chunk_text=row["chunk_text"],
                token_count=row["token_count"],
                metadata=row["metadata"] or {},
                ticker=row["ticker"],
                company_name=row["company_name"],
                fiscal_year=row["fiscal_year"],
                filing_type=row["filing_type"],
                filing_date=row["filing_date"],
                score=float(row["rank"]),
                search_type="keyword",
            )
        )

    logger.debug("Keyword search returned %d candidates", len(results))
    return results


def fetch_neighbor_chunks(
    conn: Connection,
    document_id: uuid.UUID,
    chunk_indices: Sequence[int],
) -> dict[int, str]:
    """Fetch chunk texts by document_id and chunk_index for context window expansion."""
    if not chunk_indices:
        return {}

    sql = text("""
        SELECT chunk_index, chunk_text
        FROM document_chunks
        WHERE document_id = :doc_id
          AND chunk_index = ANY(:indices);
    """)

    rows = conn.execute(
        sql,
        {"doc_id": document_id, "indices": list(chunk_indices)},
    ).fetchall()

    return {row[0]: row[1] for row in rows}
