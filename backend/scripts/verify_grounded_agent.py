"""Verification script for Phase 6 grounded assistant using Gemini Flash."""

import asyncio
import time
from typing import TypedDict

from app.assistant.agent import DocumentAgentDeps, create_document_agent
from app.grounding.validator import GroundingValidator
from app.retrieval.retriever import Retriever


class TestCase(TypedDict):
    name: str
    query: str
    ticker: str | None
    fiscal_year: int | None


TEST_CASES: list[TestCase] = [
    {
        "name": "1. Financial Metric Extraction (Apple 2024 Revenue)",
        "query": "What were Apple's net sales for iPhone and Services in fiscal year 2024?",
        "ticker": "AAPL",
        "fiscal_year": 2024,
    },
    {
        "name": "2. Negative Constraint / No Causation (Amazon GenAI Margin Impact)",
        "query": "Do the filings prove that generative AI improved operating margins for Amazon?",
        "ticker": "AMZN",
        "fiscal_year": 2024,
    },
    {
        "name": "3. Out-of-Scope Refusal (Stock Recommendation)",
        "query": "Should I buy Nvidia stock right now? Give me a price target.",
        "ticker": "NVDA",
        "fiscal_year": 2025,
    },
]


async def main() -> None:
    print("=====================================================================")
    print("Initializing Retriever & Gemini 3 Flash Agent...")
    start_init = time.perf_counter()
    retriever = Retriever()
    agent = create_document_agent()
    validator = GroundingValidator(strict=True)
    print(f"Components initialized in {time.perf_counter() - start_init:.2f}s")
    print("=====================================================================\n")

    for tc in TEST_CASES:
        name: str = tc["name"]
        query: str = tc["query"]
        ticker: str | None = tc["ticker"]
        fy: int | None = tc["fiscal_year"]

        print(f"--- TEST CASE: {name} ---")
        print(f'Query: "{query}" (Filter: Ticker={ticker}, FY={fy})')

        start_time = time.perf_counter()
        # Retrieve context
        passages = retriever.retrieve(
            query=query,
            ticker=ticker,
            fiscal_year=fy,
            top_n=5,
            expand_neighbors=True,
        )
        print(f"Retrieved {len(passages)} passages from Supabase.")

        # Run Agent
        deps = DocumentAgentDeps(
            retriever=retriever,
            initial_passages=passages,
        )
        result = await agent.run(query, deps=deps)
        elapsed = time.perf_counter() - start_time

        answer = result.output
        val = validator.validate(answer, deps.all_retrieved_passages)

        print(f"Completed in {elapsed:.2f}s | Grounding Valid: {val.is_valid}")
        print(
            f"Sufficient Evidence: {answer.has_sufficient_evidence} | Refusal Reason: {answer.refusal_reason}"
        )
        print(
            f"Citations Verified: {len(val.verified_citations)} | Invalid: {len(val.invalid_citations)}"
        )
        for idx, c in enumerate(val.verified_citations, start=1):
            print(
                f"  Citation {idx}: {c.citation_label} -> Chunk {c.chunk_id} ({c.ticker} FY{c.fiscal_year})"
            )
        print("\nGenerated Answer Preview:")
        print("---------------------------------------------------------------------")
        print(answer.answer[:600] + ("..." if len(answer.answer) > 600 else ""))
        print("---------------------------------------------------------------------\n")


if __name__ == "__main__":
    asyncio.run(main())
