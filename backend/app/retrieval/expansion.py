"""Financial query expansion and GAAP line-item synonym mapping."""

import re

# Domain-specific mapping: ONLY expand true abbreviations and colloquial terms
FINANCIAL_ACRONYMS: dict[str, str] = {
    "capex": "property and equipment",
    "capital expenditure": "property and equipment",
    "capital expenditures": "property and equipment",
    "buyback": "repurchase of common stock",
    "buybacks": "repurchases of common stock",
    "rpo": "remaining performance obligations",
    "cogs": "cost of sales",
    "ebitda": "operating income",
    "ppe": "property and equipment",
    "advertising": "ads",
    "ad revenue": "advertising ads",
    "ad revenues": "advertising ads",
}


def expand_financial_query(query: str) -> tuple[str, str]:
    """Expand user query with official SEC GAAP line-item synonyms.

    Args:
        query: Raw user query string.

    Returns:
        tuple of (semantic_query, fts_query):
        - semantic_query: The query used for dense vector embedding.
        - fts_query: The query used for PostgreSQL full-text search.
    """
    clean_query = " ".join(query.split())
    query_lower = clean_query.lower()

    fts_query = clean_query
    semantic_query = clean_query

    # Replace abbreviations with official GAAP terms
    for acronym, official_term in FINANCIAL_ACRONYMS.items():
        pattern = r"\b" + re.escape(acronym) + r"\b"
        if re.search(pattern, query_lower):
            # For FTS, replace the abbreviation with the GAAP term or add it as alternative
            fts_query = re.sub(pattern, f'"{official_term}"', fts_query, flags=re.IGNORECASE)
            semantic_query = f"{clean_query} {official_term}"
            break

    return semantic_query, fts_query
