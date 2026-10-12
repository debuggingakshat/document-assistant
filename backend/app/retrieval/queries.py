"""Database query operations for semantic and full-text keyword retrieval."""

from collections.abc import Sequence
import logging
import re
from typing import Any
import uuid

from sqlalchemy import Connection, text

from app.retrieval.models import RetrievedChunk

logger = logging.getLogger(__name__)

# Common conversational and grammatical stopwords to exclude from keyword extraction
FTS_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "as",
    "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can",
    "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from", "further",
    "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him", "himself", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me", "more", "most", "my",
    "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or", "other", "our",
    "ours", "ourselves", "out", "over", "own", "same", "she", "should", "so", "some", "such", "than",
    "that", "the", "their", "theirs", "them", "themselves", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "will", "with", "you", "your", "yours",
    "yourself", "yourselves", "please", "tell", "show", "explain", "describe", "give", "filing", "filings",
    "prove", "state", "say", "according", "evidence", "report", "reports", "document", "documents",
}


def extract_salient_keywords(query: str) -> list[str]:
    """Extract informative keyword tokens from a natural language user query."""
    # Find all alphanumeric tokens (including hyphenated financial terms like 10-K)
    tokens = re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", query)
    keywords: list[str] = []
    for t in tokens:
        clean_t = t.strip("-").lower()
        if clean_t and clean_t not in FTS_STOPWORDS and not clean_t.isdigit():
            keywords.append(clean_t)
        elif t.isdigit() and len(t) == 4:  # Preserve years like 2024
            keywords.append(t)
    return keywords


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
    """Execute Postgres full-text search with keyword extraction and fallback OR ranking."""
    clean_query = " ".join(query_text.split())
    if not clean_query:
        return []

    salient_keywords = extract_salient_keywords(clean_query)
    # Prefer extracted keywords for clean FTS, falling back to clean_query if none extracted
    effective_query_text = " ".join(salient_keywords) if salient_keywords else clean_query

    where_clauses: list[str] = [
        "dc.search_vector @@ websearch_to_tsquery('english', :query_text)"
    ]
    params: dict[str, Any] = {
        "query_text": effective_query_text,
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
    seen_ids: set[uuid.UUID] = set()

    for row in rows:
        seen_ids.add(row["id"])
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

    # If strict search returned fewer than 5 rows, run multi-term OR fallback
    if len(results) < 5 and len(salient_keywords) >= 2:
        or_expr = " | ".join(salient_keywords[:8])
        or_where: list[str] = [
            "dc.search_vector @@ to_tsquery('english', :or_expr)"
        ]
        or_params: dict[str, Any] = {
            "or_expr": or_expr,
            "limit": limit - len(results),
        }
        if ticker:
            or_where.append("sd.ticker = :ticker")
            or_params["ticker"] = ticker.upper()
        if fiscal_year is not None:
            or_where.append("sd.fiscal_year = :fiscal_year")
            or_params["fiscal_year"] = fiscal_year

        or_where_sql = f"WHERE {' AND '.join(or_where)}"
        fallback_sql = f"""
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
                ts_rank_cd(dc.search_vector, to_tsquery('english', :or_expr)) AS rank
            FROM document_chunks dc
            JOIN source_documents sd ON dc.document_id = sd.id
            {or_where_sql}
            ORDER BY rank DESC
            LIMIT :limit;
        """
        try:
            fallback_rows = conn.execute(text(fallback_sql), or_params).mappings().fetchall()
            for row in fallback_rows:
                if row["id"] not in seen_ids:
                    seen_ids.add(row["id"])
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
        except Exception as e:
            logger.debug("OR fallback query skipped due to syntax: %s", e)

    logger.debug("Keyword search returned %d candidates", len(results))
    return results[:limit]


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
