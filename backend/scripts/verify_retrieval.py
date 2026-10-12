"""Verification script for Phase 5 hybrid retrieval against live Supabase database."""

import time
from typing import TypedDict

from app.retrieval.retriever import Retriever


class QueryCase(TypedDict):
    query: str
    ticker: str
    fiscal_year: int
    description: str


TEST_QUERIES: list[QueryCase] = [
    {
        "query": "revenue mix iPhone Services Mac iPad Wearables",
        "ticker": "AAPL",
        "fiscal_year": 2024,
        "description": "Apple 2024 product & services revenue breakdown",
    },
    {
        "query": "Data Center revenue customer concentration compute demand",
        "ticker": "NVDA",
        "fiscal_year": 2025,
        "description": "Nvidia 2025 Data Center drivers & customers",
    },
    {
        "query": "AWS operating income and net sales segment results",
        "ticker": "AMZN",
        "fiscal_year": 2024,
        "description": "Amazon 2024 AWS segment profitability",
    },
    {
        "query": "Azure cloud revenue Intelligent Cloud server products",
        "ticker": "MSFT",
        "fiscal_year": 2024,
        "description": "Microsoft 2024 Azure & Intelligent Cloud growth",
    },
    {
        "query": "Google Cloud and YouTube advertising revenues",
        "ticker": "GOOGL",
        "fiscal_year": 2024,
        "description": "Alphabet 2024 Google Cloud & YouTube ad trends",
    },
]


def main() -> None:
    print("=====================================================================")
    print("Initializing Retriever (loading local BGE model on Apple Silicon MPS)...")
    start_init = time.perf_counter()
    retriever = Retriever()
    print(f"Retriever initialized in {time.perf_counter() - start_init:.2f}s")
    print("=====================================================================\n")

    for i, tq in enumerate(TEST_QUERIES, start=1):
        query: str = tq["query"]
        ticker: str = tq["ticker"]
        fy: int = tq["fiscal_year"]
        desc: str = tq["description"]

        print(f"[{i}/{len(TEST_QUERIES)}] Query: '{query}'")
        print(f"    Target: {desc} (Ticker: {ticker}, FY: {fy})")

        start_q = time.perf_counter()
        passages = retriever.retrieve(
            query=query,
            ticker=ticker,
            fiscal_year=fy,
            top_n=3,
            expand_neighbors=True,
        )
        latency = (time.perf_counter() - start_q) * 1000

        print(f"    Retrieved: {len(passages)} passages in {latency:.1f}ms")
        for rank, p in enumerate(passages, start=1):
            table_badge = "[TABLE]" if p.is_table else "[TEXT]"
            print(
                f"      Top {rank} {table_badge} (RRF Score: {p.rrf_score:.5f}) | {p.citation_source}"
            )
            snippet = p.text.replace("\n", " ")[:140]
            print(f'        Snippet: "{snippet}..."')
        print()

    print("=====================================================================")
    print("Retrieval verification completed successfully!")
    print("=====================================================================")


if __name__ == "__main__":
    main()
