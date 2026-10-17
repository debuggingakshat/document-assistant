"""Unit tests for financial query expansion."""

from app.retrieval.expansion import expand_financial_query


def test_expand_financial_query_capex() -> None:
    query = "Amazon capex 2024"
    expanded_semantic, fts_query = expand_financial_query(query)
    assert "property and equipment" in expanded_semantic
    assert '"property and equipment"' in fts_query


def test_expand_financial_query_buyback() -> None:
    query = "Apple buybacks in fiscal 2024"
    expanded_semantic, fts_query = expand_financial_query(query)
    assert "repurchases of common stock" in expanded_semantic
    assert '"repurchases of common stock"' in fts_query


def test_expand_financial_query_no_match() -> None:
    query = "Who is the CEO of Apple?"
    expanded_semantic, fts_query = expand_financial_query(query)
    assert expanded_semantic == query
    assert fts_query == query
