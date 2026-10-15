"""Automated Smoke-Test for Meridian Research 10 Client-Brief Analyst Questions.

Tests all 10 representative equity research analyst questions from docs/client-brief.md:
1. AAPL revenue mix change (2021-2025)
2. AMZN AWS operating income/margin vs NA & Int'l (2021-2025)
3. NVDA Data Center demand drivers, concentration, supply constraints (2021-2025)
4. MSFT Azure & AI infrastructure description changes (2021-2025)
5. GOOGL segment revenue trends (2021-2025)
6. Multi-company risk factor changes (AI, export controls, supply chain)
7. AAPL & NVDA supplier concentration & third-party manufacturing
8. MSFT, GOOGL, AMZN, NVDA capex & purchase commitments
9. Geographic revenue exposures & YoY shifts in latest 10-K
10. Generative AI margin causality (refusal to infer beyond filings)
"""

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass
from typing import Any

from app.assistant.agent import DocumentAgentDeps, create_document_agent
from app.chat.orchestrator import _extract_ticker_and_fy, _run_agent_with_failover
from app.grounding.validator import GroundingValidator
from app.retrieval.retriever import Retriever


@dataclass
class QuestionCase:
    number: int
    title: str
    query: str
    expected_ticker: str | None
    check_refusal: bool = False


QUESTIONS: list[QuestionCase] = [
    QuestionCase(
        number=1,
        title="Apple Revenue Mix (iPhone, Services, Mac, iPad, Wearables)",
        query="Across Apple's 2021–2025 10-Ks, how did the revenue mix between iPhone, Services, Mac, iPad, and Wearables change, and which category appears to have contributed most to any mix shift?",
        expected_ticker="AAPL",
    ),
    QuestionCase(
        number=2,
        title="Amazon AWS vs NA & International Operating Margins",
        query="For Amazon, compare AWS operating income and margin against North America and International from 2021–2025. In which years did AWS appear to fund losses or weaker profitability elsewhere?",
        expected_ticker="AMZN",
    ),
    QuestionCase(
        number=3,
        title="NVIDIA Data Center Demand Drivers & Constraints",
        query="How did NVIDIA describe demand drivers, customer concentration, and supply constraints for its Data Center business from fiscal 2021 through fiscal 2025?",
        expected_ticker="NVDA",
    ),
    QuestionCase(
        number=4,
        title="Microsoft Azure & AI Cloud Infrastructure Evolution",
        query="Across Microsoft's 2021–2025 filings, what changed in the way the company describes Azure, AI infrastructure, and cloud capacity constraints?",
        expected_ticker="MSFT",
    ),
    QuestionCase(
        number=5,
        title="Alphabet Segment Revenue Trends (Search, YouTube, Cloud)",
        query="For Alphabet, how did Google Search, YouTube ads, Google Network, subscriptions/platforms/devices, and Google Cloud revenue trends differ across the available 10-Ks?",
        expected_ticker="GOOGL",
    ),
    QuestionCase(
        number=6,
        title="Material Risk-Factor Language Changes (AI, Export, Supply)",
        query="Which of the five companies added, removed, or materially changed risk-factor language related to AI, cloud infrastructure, export controls, supply chain concentration, or regulation between 2021 and 2025?",
        expected_ticker=None,
    ),
    QuestionCase(
        number=7,
        title="Apple & NVIDIA Supplier Concentration & Manufacturing",
        query="For Apple and NVIDIA, what do the filings say about supplier concentration or dependence on third-party manufacturing, and did the wording become more or less urgent over time?",
        expected_ticker=None,
    ),
    QuestionCase(
        number=8,
        title="Capex & Purchase Commitments Comparison (Scale/Timing)",
        query="Compare capital expenditures and purchase commitments for Microsoft, Alphabet, Amazon, and NVIDIA. What do the filings imply about the scale and timing of AI/cloud infrastructure investment?",
        expected_ticker=None,
    ),
    QuestionCase(
        number=9,
        title="Geographic Revenue Exposures & YoY Shifts in Latest 10-K",
        query="For each company, summarize the most important geographic revenue exposures disclosed in the latest 10-K, then identify any year-over-year changes that could matter to an analyst.",
        expected_ticker=None,
    ),
    QuestionCase(
        number=10,
        title="GenAI Margin Causality (Corpus Evidence & Refusal)",
        query="If an analyst asks whether the filings prove that generative AI improved margins for any of these companies, what evidence exists in the corpus, and where should the bot refuse to infer beyond the filings?",
        expected_ticker=None,
        check_refusal=True,
    ),
]


async def run_single_question(
    q: QuestionCase,
    retriever: Retriever,
    agent: Any,
    validator: GroundingValidator,
) -> dict[str, Any]:
    print(f"\n{'='*70}")
    print(f"[Question {q.number}/10] {q.title}")
    print(f"Query: {q.query}")

    t_start = time.perf_counter()

    # 1. Extract filters & retrieve
    inferred_ticker, inferred_fy = _extract_ticker_and_fy(q.query)
    passages = retriever.retrieve(
        query=q.query,
        ticker=inferred_ticker,
        fiscal_year=inferred_fy,
        top_n=6,
        expand_neighbors=True,
    )
    t_retrieved = time.perf_counter()
    retrieval_dur = t_retrieved - t_start

    print(f"Filters: ticker={inferred_ticker}, fy={inferred_fy} | Retrieved: {len(passages)} passages ({retrieval_dur:.2f}s)")

    # 2. Run agent with failover
    deps = DocumentAgentDeps(
        retriever=retriever,
        initial_passages=passages,
    )

    agent_res = await _run_agent_with_failover(agent, q.query, deps)
    answer = agent_res.output
    t_llm = time.perf_counter()
    llm_dur = t_llm - t_retrieved
    total_dur = t_llm - t_start

    # 3. Grounding validation
    val = validator.validate(answer, deps.all_retrieved_passages)

    # 4. Check refusal / negative constraint for Q10
    refusal_pass = True
    if q.check_refusal:
        lower_ans = answer.answer.lower()
        # Should caution against proving causality or state filings do not prove causality
        causality_refused = any(
            phrase in lower_ans
            for phrase in [
                "not prove",
                "cannot prove",
                "refuse",
                "does not establish",
                "caution",
                "correlation",
                "do not prove",
                "no direct proof",
                "not isolate",
                "unsubstantiated",
                "insufficient",
                "no evidence",
                "cannot be inferred",
            ]
        )
        refusal_pass = causality_refused

    if q.check_refusal:
        passed = refusal_pass and len(val.invalid_citations) == 0
    else:
        passed = len(val.verified_citations) > 0

    print(f"Completed in {total_dur:.2f}s (Retrieval: {retrieval_dur:.2f}s, LLM: {llm_dur:.2f}s)")
    print(f"Verified Citations: {len(val.verified_citations)} | Invalid: {len(val.invalid_citations)}")
    if q.check_refusal:
        print(f"Refusal to infer non-causal margin impact verified: {refusal_pass}")

    preview = answer.answer[:300].replace("\n", " ")
    print(f"Excerpt: {preview}...")
    print(f"Status: {'[PASS]' if passed else '[FAIL]'}")

    return {
        "number": q.number,
        "title": q.title,
        "ticker": inferred_ticker or "ALL",
        "passages": len(passages),
        "citations": len(val.verified_citations),
        "invalid_citations": len(val.invalid_citations),
        "latency_s": round(total_dur, 2),
        "passed": passed,
        "refusal_pass": refusal_pass if q.check_refusal else None,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Client Brief Smoke Test")
    parser.add_argument("--question", type=int, help="Test a specific question number (1-10)")
    parser.add_argument("--quick", action="store_true", help="Run questions 1, 2, and 10 only")
    args = parser.parse_args()

    print("Initializing Retriever, Agent, and GroundingValidator...")
    t0 = time.perf_counter()
    retriever = Retriever()
    agent = create_document_agent()
    validator = GroundingValidator(strict=False)
    print(f"Initialized in {time.perf_counter() - t0:.2f}s")

    if args.question:
        targets = [q for q in QUESTIONS if q.number == args.question]
    elif args.quick:
        targets = [q for q in QUESTIONS if q.number in (1, 2, 10)]
    else:
        targets = QUESTIONS

    print(f"Running smoke test for {len(targets)} question(s)...")

    results: list[dict[str, Any]] = []
    for q in targets:
        try:
            res = await run_single_question(q, retriever, agent, validator)
            results.append(res)
        except Exception as exc:
            print(f"[ERROR] Question {q.number} failed with exception: {exc}")
            results.append({
                "number": q.number,
                "title": q.title,
                "ticker": "ERROR",
                "passages": 0,
                "citations": 0,
                "invalid_citations": 0,
                "latency_s": 0.0,
                "passed": False,
            })

    # Summary table
    print("\n" + "="*82)
    print("SMOKE TEST SUMMARY RESULTS (Client Brief 10 Questions)")
    print("="*82)
    print(f"{'#':<3} | {'Question Title':<42} | {'Ticker':<6} | {'Cits':<4} | {'Time':<6} | {'Status'}")
    print("-"*82)
    passed_count = 0
    for r in results:
        status_str = "PASS" if r["passed"] else "FAIL"
        if r["passed"]:
            passed_count += 1
        print(f"{r['number']:<3} | {r['title'][:42]:<42} | {r['ticker']:<6} | {r['citations']:<4} | {r['latency_s']:>4.1f}s | {status_str}")
    print("-"*82)
    print(f"Total: {passed_count}/{len(results)} passed.")
    print("="*82)

    if passed_count < len(results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
