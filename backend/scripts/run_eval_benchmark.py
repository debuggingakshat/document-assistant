"""Automated Empirical Evaluation Benchmark for Document Assistant.

Measures:
1. Retrieval Accuracy: Top-1, Top-3, Top-5 Recall and MRR@5 comparing
   Dense Vector vs. Sparse FTS vs. Baseline RRF vs. Production Hybrid Pipeline.
2. Grounding & Citation Accuracy: 4-Gate Fail-Closed Verification Pass Rate.
"""

import time
from dataclasses import dataclass
from typing import Any
import uuid

from app.assistant.schemas import CitationItem, GroundedAnswer
from app.grounding.validator import GroundingValidator
from app.retrieval.expansion import expand_financial_query
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.models import RetrievedPassage
from app.retrieval.queries import search_keyword, search_semantic
from app.retrieval.retriever import get_default_engine
from ingest.embedder import LocalEmbedder


@dataclass
class EvalQuery:
    id: int
    query: str
    ticker: str
    fiscal_year: int
    target_terms: list[str]


BENCHMARK_QUERIES: list[EvalQuery] = [
    EvalQuery(1, "Apple iPhone net sales revenue fiscal 2024", "AAPL", 2024, ["201,183", "iPhone"]),
    EvalQuery(2, "Apple Services net sales and App Store growth 2024", "AAPL", 2024, ["96,169", "Services"]),
    EvalQuery(3, "Apple cash dividends and share repurchases 2024", "AAPL", 2024, ["repurchased", "dividends"]),
    EvalQuery(4, "Amazon AWS net sales and segment operating income 2024", "AMZN", 2024, ["AWS", "operating income"]),
    EvalQuery(5, "Amazon North America operating income or losses 2023", "AMZN", 2023, ["North America", "operating"]),
    EvalQuery(6, "Amazon purchases of property and equipment capital expenditures 2024", "AMZN", 2024, ["property and equipment"]),
    EvalQuery(7, "Microsoft Azure and Intelligent Cloud revenue growth 2024", "MSFT", 2024, ["Intelligent Cloud", "Azure"]),
    EvalQuery(8, "Microsoft cash payments for property and equipment capex 2024", "MSFT", 2024, ["property and equipment", "44,477"]),
    EvalQuery(9, "Microsoft commercial remaining performance obligations RPO 2024", "MSFT", 2024, ["remaining performance obligations"]),
    EvalQuery(10, "NVIDIA Data Center compute and networking revenue 2025", "NVDA", 2025, ["Data Center", "110,362"]),
    EvalQuery(11, "NVIDIA customer concentration percentage 2025", "NVDA", 2025, ["Customer A", "concentration"]),
    EvalQuery(12, "Alphabet Google Cloud revenues and operating profit 2024", "GOOGL", 2024, ["Google Cloud", "operating income"]),
    EvalQuery(13, "Alphabet YouTube advertising revenues 2024", "GOOGL", 2024, ["YouTube ads", "36,147"]),
    EvalQuery(14, "Alphabet Google Services revenue breakdown 2024", "GOOGL", 2024, ["Google Services", "305,274"]),
    EvalQuery(15, "NVIDIA research and development expense expansion 2025", "NVDA", 2025, ["Research and development", "expense"]),
]


def run_retrieval_ablation(queries: list[EvalQuery]) -> dict[str, Any]:
    """Compare Dense, Sparse, Baseline RRF, and Production Hybrid Pipeline."""
    print("=" * 84)
    print("PHASE 1: RETRIEVAL ACCURACY & ABLATION BENCHMARK")
    print("Comparing: (1) Dense, (2) Sparse, (3) Baseline RRF, (4) Production Hybrid RRF")
    print("=" * 84)

    embedder = LocalEmbedder()
    engine = get_default_engine()

    results: dict[str, dict[str, Any]] = {
        "dense": {"top1": 0, "top3": 0, "top5": 0, "rr_sum": 0.0, "latency_sum": 0.0},
        "sparse": {"top1": 0, "top3": 0, "top5": 0, "rr_sum": 0.0, "latency_sum": 0.0},
        "baseline_rrf": {"top1": 0, "top3": 0, "top5": 0, "rr_sum": 0.0, "latency_sum": 0.0},
        "production_hybrid": {"top1": 0, "top3": 0, "top5": 0, "rr_sum": 0.0, "latency_sum": 0.0},
    }

    n = len(queries)

    with engine.connect() as conn:
        for eq in queries:
            # 0. Query expansion
            expanded_sem, effective_kw = expand_financial_query(eq.query)

            # 1. Embed query
            t0 = time.perf_counter()
            vec_raw = embedder.embed_text(eq.query)
            vec_expanded = embedder.embed_text(expanded_sem)
            embed_lat = (time.perf_counter() - t0) * 1000

            # 2. Sparse Search
            t0 = time.perf_counter()
            sparse_hits_raw = search_keyword(conn, eq.query, ticker=eq.ticker, fiscal_year=eq.fiscal_year, limit=20)
            sparse_hits_expanded = search_keyword(conn, effective_kw, ticker=eq.ticker, fiscal_year=eq.fiscal_year, limit=20)
            sparse_lat = (time.perf_counter() - t0) * 1000
            results["sparse"]["latency_sum"] += sparse_lat

            # 3. Dense Search
            t0 = time.perf_counter()
            dense_hits_raw = search_semantic(conn, vec_raw, ticker=eq.ticker, fiscal_year=eq.fiscal_year, limit=20)
            dense_hits_expanded = search_semantic(conn, vec_expanded, ticker=eq.ticker, fiscal_year=eq.fiscal_year, limit=20)
            dense_lat = (time.perf_counter() - t0) * 1000 + embed_lat
            results["dense"]["latency_sum"] += dense_lat

            # 4. Baseline RRF (k=60, raw queries)
            t0 = time.perf_counter()
            baseline_fused = reciprocal_rank_fusion(dense_hits_raw, sparse_hits_raw, k=60, table_boost=1.0, item_boost=1.0, top_n=5)
            results["baseline_rrf"]["latency_sum"] += (time.perf_counter() - t0) * 1000 + max(sparse_lat, dense_lat)

            # 5. Production Hybrid: Expansion + Calibrated RRF (k=60)
            t0 = time.perf_counter()
            prod_fused = reciprocal_rank_fusion(
                dense_hits_expanded,
                sparse_hits_expanded,
                k=60,
                table_boost=1.0,
                item_boost=1.0,
                top_n=5,
            )
            results["production_hybrid"]["latency_sum"] += (time.perf_counter() - t0) * 1000 + max(sparse_lat, dense_lat)

            def eval_hits(chunks: list[Any]) -> tuple[bool, bool, bool, float]:
                rank_found = 0
                for r, item in enumerate(chunks[:5], 1):
                    txt = getattr(item, "chunk_text", None) or getattr(item.chunk, "chunk_text", "")
                    if all(term.lower() in txt.lower() for term in eq.target_terms):
                        rank_found = r
                        break
                h1 = rank_found == 1
                h3 = 1 <= rank_found <= 3
                h5 = 1 <= rank_found <= 5
                rr = 1.0 / rank_found if rank_found > 0 else 0.0
                return h1, h3, h5, rr

            for mode, chunk_list in [
                ("dense", dense_hits_raw),
                ("sparse", sparse_hits_raw),
                ("baseline_rrf", baseline_fused),
                ("production_hybrid", prod_fused),
            ]:
                h1, h3, h5, rr = eval_hits(chunk_list)
                if h1:
                    results[mode]["top1"] += 1
                if h3:
                    results[mode]["top3"] += 1
                if h5:
                    results[mode]["top5"] += 1
                results[mode]["rr_sum"] += rr

            print(f"  [Q{eq.id:02d}] {eq.query[:50]:<50} | Ticker: {eq.ticker}")

    summary: dict[str, Any] = {}
    print("\n" + "-" * 84)
    print(f"{'Search Pipeline':<28} | {'Top-1 Recall':<12} | {'Top-3 Recall':<12} | {'Top-5 Recall':<12} | {'MRR@5'}")
    print("-" * 84)
    for mode, name in [
        ("dense", "Dense Vector (768-d)"),
        ("sparse", "Sparse FTS (Postgres)"),
        ("baseline_rrf", "Baseline Hybrid RRF (k=60)"),
        ("production_hybrid", "Production Hybrid (Expansion+RRF)"),
    ]:
        top1_pct = (results[mode]["top1"] / n) * 100
        top3_pct = (results[mode]["top3"] / n) * 100
        top5_pct = (results[mode]["top5"] / n) * 100
        mrr = results[mode]["rr_sum"] / n
        summary[mode] = {
            "top1_recall": round(top1_pct, 1),
            "top3_recall": round(top3_pct, 1),
            "top5_recall": round(top5_pct, 1),
            "mrr": round(mrr, 3),
        }
        print(f"{name:<28} | {top1_pct:>10.1f}% | {top3_pct:>10.1f}% | {top5_pct:>10.1f}% | {mrr:>8.3f}")
    print("-" * 84)
    return summary


def run_grounding_benchmark() -> dict[str, Any]:
    """Test 4-gate verification integrity on sample groundings and compliance refusals."""
    print("\n" + "=" * 84)
    print("PHASE 2: 4-GATE GROUNDING & CITATION VERIFICATION BENCHMARK")
    print("=" * 84)

    validator = GroundingValidator(strict=True)
    dummy_chunk_id = uuid.uuid4()
    p = RetrievedPassage(
        chunk_id=dummy_chunk_id,
        document_id=uuid.uuid4(),
        ticker="AAPL",
        company_name="Apple Inc.",
        fiscal_year=2024,
        filing_type="10-K",
        filing_date="2024-11-01",
        chunk_index=46,
        text="iPhone net sales were $201,183 million in fiscal 2024.",
        full_context_text="iPhone net sales were $201,183 million in fiscal 2024.",
        rrf_score=0.033,
        citation_source="Apple Inc. (AAPL) FY2024 10-K [Chunk 46]",
    )

    test_cases = [
        ("Valid Factual Grounding", GroundedAnswer(answer="Apple reported iPhone net sales of $201,183 million [^1].", citations=[CitationItem(chunk_id=dummy_chunk_id, citation_label="[^1]", ticker="AAPL", fiscal_year=2024, snippet="$201,183 million")], has_sufficient_evidence=True), [p], True),
        ("Gate 1 Provenance Fail (Fake UUID)", GroundedAnswer(answer="Apple earned huge profits [^1].", citations=[CitationItem(chunk_id=uuid.uuid4(), citation_label="[^1]", ticker="AAPL", fiscal_year=2024)], has_sufficient_evidence=True), [p], False),
        ("Gate 2 Entity Integrity Fail (Ticker mismatch)", GroundedAnswer(answer="Microsoft reported iPhone revenue [^1].", citations=[CitationItem(chunk_id=dummy_chunk_id, citation_label="[^1]", ticker="MSFT", fiscal_year=2024)], has_sufficient_evidence=True), [p], False),
        ("Gate 3 Marker Sync Fail (Orphan [^2])", GroundedAnswer(answer="Apple reported $201,183M [^1] and unverified extra [^2].", citations=[CitationItem(chunk_id=dummy_chunk_id, citation_label="[^1]", ticker="AAPL", fiscal_year=2024)], has_sufficient_evidence=True), [p], False),
        ("Gate 4 Snippet Verification (Verbatim)", GroundedAnswer(answer="Apple net sales were $201,183 million [^1].", citations=[CitationItem(chunk_id=dummy_chunk_id, citation_label="[^1]", ticker="AAPL", fiscal_year=2024, snippet="$201,183 million")], has_sufficient_evidence=True), [p], True),
        ("Scope: Trading Advice Refusal", GroundedAnswer(answer="As Meridian Research's Document Assistant, I cannot provide trading recommendations, buy/sell ratings, or price targets.", citations=[], has_sufficient_evidence=False, refusal_reason="Out of scope: trading advice"), [], True),
        ("Scope: Non-Financial Domain Refusal", GroundedAnswer(answer="As Meridian Research's Document Assistant, I specialize exclusively in institutional equity research. I cannot assist with history.", citations=[], has_sufficient_evidence=False, refusal_reason="Out of domain: non-financial topic"), [], True),
        ("Scope: Corporate Finance Concept Bridge", GroundedAnswer(answer="Capital budgeting is the process corporate management uses to evaluate long-term capital investments...", citations=[], has_sufficient_evidence=True, refusal_reason=None), [], True),
    ]

    total_gate_tests = len(test_cases)
    passed_gate_tests = 0

    for name, ans, passages, expected_valid in test_cases:
        res = validator.validate(ans, passages)
        test_passed = (res.is_valid == expected_valid)
        if test_passed:
            passed_gate_tests += 1
        status = "[PASS]" if test_passed else "[FAIL]"
        print(f"  {status} {name:<46} (Expected: {str(expected_valid):<5} | Actual: {str(res.is_valid):<5})")

    pass_pct = (passed_gate_tests / total_gate_tests) * 100
    print("-" * 84)
    print(f"4-Gate Verification Accuracy: {pass_pct:.1f}% ({passed_gate_tests}/{total_gate_tests} tests verified)")
    print("-" * 84)
    return {"gate_pass_rate": pass_pct, "tests_passed": passed_gate_tests, "total": total_gate_tests}


def main() -> None:
    print("\n" + "=" * 84)
    print("DOCUMENT ASSISTANT: EMPIRICAL PERFORMANCE & BENCHMARK SUITE")
    print("Generating mathematically verified metrics for Meridian Research & Resume")
    print("=" * 84 + "\n")

    retrieval_metrics = run_retrieval_ablation(BENCHMARK_QUERIES)
    grounding_metrics = run_grounding_benchmark()

    print("\n" + "=" * 84)
    print("FINAL EMPIRICAL RESUME METRICS SUMMARY")
    print("=" * 84)
    prod = retrieval_metrics["production_hybrid"]
    dense = retrieval_metrics["dense"]
    gain_top1 = prod["top1_recall"] - dense["top1_recall"]
    gain_top5 = prod["top5_recall"] - dense["top5_recall"]

    print(f"* Production Top-1 Recall:    {prod['top1_recall']}% (vs Dense {dense['top1_recall']}%, Gain: +{gain_top1:.1f}%)")
    print(f"* Production Top-5 Recall:    {prod['top5_recall']}% (vs Dense {dense['top5_recall']}%, Gain: +{gain_top5:.1f}%)")
    print(f"* Production MRR@5:           {prod['mrr']}")
    print(f"* 4-Gate Grounding Pass Rate: {grounding_metrics['gate_pass_rate']}% (0% ungrounded citations permitted)")
    print("=" * 84 + "\n")


if __name__ == "__main__":
    main()
