"""Unit tests for chat turn orchestrator with mocked dependencies."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.assistant.schemas import CitationItem, GroundedAnswer
from app.chat.orchestrator import orchestrate_turn, stream_orchestrated_turn
from app.grounding.validator import GroundingValidator
from app.retrieval.models import RetrievedPassage


def _mock_passage(cid: uuid.UUID) -> RetrievedPassage:
    return RetrievedPassage(
        chunk_id=cid,
        document_id=uuid.uuid4(),
        ticker="AAPL",
        company_name="Apple Inc.",
        fiscal_year=2024,
        filing_type="10-K",
        filing_date="2024-11-01",
        chunk_index=1,
        text="iPhone net sales were $201,183 million in fiscal 2024.",
        full_context_text="iPhone net sales were $201,183 million in fiscal 2024.",
        rrf_score=0.032,
        citation_source="Apple Inc. (AAPL) FY2024 10-K [Item 7. MD&A]",
    )


@pytest.mark.anyio
async def test_orchestrate_turn_flow() -> None:
    """Verifies end-to-end turn coordination from user msg to citation persistence."""
    thread_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    passage = _mock_passage(chunk_id)

    # 1. Mock Supabase client
    mock_client = MagicMock()
    # Mock insert user message
    mock_user_msg = {
        "id": str(uuid.uuid4()),
        "thread_id": str(thread_id),
        "role": "user",
    }
    mock_asst_msg = {
        "id": str(uuid.uuid4()),
        "thread_id": str(thread_id),
        "role": "assistant",
    }
    mock_client.table().insert().execute.side_effect = [
        MagicMock(data=[mock_user_msg]),  # user message insert
        MagicMock(data=[mock_asst_msg]),  # asst message insert
        MagicMock(data=[{"id": str(uuid.uuid4())}]),  # citations insert
    ]

    # 2. Mock Retriever
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = [passage]

    # 3. Mock Agent
    mock_agent = MagicMock()
    answer = GroundedAnswer(
        answer="Apple reported iPhone revenue of $201,183M [^1].",
        citations=[
            CitationItem(
                chunk_id=chunk_id,
                citation_label="[^1]",
                ticker="AAPL",
                fiscal_year=2024,
                snippet="$201,183M",
            )
        ],
        has_sufficient_evidence=True,
    )
    mock_agent_result = MagicMock()
    mock_agent_result.output = answer
    mock_agent_result.data = answer
    mock_agent.run = AsyncMock(return_value=mock_agent_result)

    # 4. Run orchestrator
    result = await orchestrate_turn(
        client=mock_client,
        thread_id=thread_id,
        user_content="What was Apple iPhone sales in 2024?",
        retriever=mock_retriever,
        validator=GroundingValidator(strict=True),
        agent_override=mock_agent,
    )

    assert result.user_message_id == uuid.UUID(mock_user_msg["id"])
    assert result.assistant_message_id == uuid.UUID(mock_asst_msg["id"])
    assert result.validation.is_valid is True
    assert len(result.validation.verified_citations) == 1
    mock_retriever.retrieve.assert_called_once()
    mock_agent.run.assert_called_once()


@pytest.mark.anyio
async def test_stream_orchestrated_turn() -> None:
    """Verifies stream yields text tokens, citation data part, and finish event."""
    thread_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    passage = _mock_passage(chunk_id)

    mock_client = MagicMock()
    mock_user_msg = {"id": str(uuid.uuid4())}
    mock_asst_msg = {"id": str(uuid.uuid4())}
    mock_client.table().insert().execute.side_effect = [
        MagicMock(data=[mock_user_msg]),
        MagicMock(data=[mock_asst_msg]),
        MagicMock(data=[{"id": str(uuid.uuid4()), "chunk_id": str(chunk_id)}]),
    ]

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = [passage]

    mock_agent = MagicMock()
    answer = GroundedAnswer(
        answer="Apple grew Services [^1].",
        citations=[
            CitationItem(
                chunk_id=chunk_id,
                citation_label="[^1]",
                ticker="AAPL",
                fiscal_year=2024,
            )
        ],
        has_sufficient_evidence=True,
    )
    mock_agent_result = MagicMock()
    mock_agent_result.output = answer
    mock_agent_result.data = answer
    mock_agent.run = AsyncMock(return_value=mock_agent_result)

    chunks = []
    async for s in stream_orchestrated_turn(
        client=mock_client,
        thread_id=thread_id,
        user_content="Services revenue?",
        retriever=mock_retriever,
        agent_override=mock_agent,
    ):
        chunks.append(s)

    full_stream = "".join(chunks)
    assert '0:"Apple' in full_stream
    assert '2:[{"type": "citations"' in full_stream
    assert 'd:{"finishReason": "stop"' in full_stream


@pytest.mark.anyio
async def test_multi_turn_ticker_inheritance() -> None:
    """Verifies that follow-up questions inherit the active ticker and context from previous turns."""
    thread_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    passage = _mock_passage(chunk_id)

    mock_client = MagicMock()
    # Mock previous messages in thread: Turn 1 was about Apple (AAPL)
    prev_user = {"role": "user", "content": "What was Apple revenue in 2024?"}
    prev_asst = {"role": "assistant", "content": "Apple revenue was $391,035M [^1]."}
    mock_client.table().select().eq().order().execute.return_value = MagicMock(
        data=[prev_user, prev_asst]
    )
    mock_client.table().insert().execute.side_effect = [
        MagicMock(data=[{"id": str(uuid.uuid4())}]),
        MagicMock(data=[{"id": str(uuid.uuid4())}]),
        MagicMock(data=[{"id": str(uuid.uuid4())}]),
    ]

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = [passage]

    mock_agent = MagicMock()
    answer = GroundedAnswer(
        answer="Comparing to 2023, Apple had lower growth [^1].",
        citations=[CitationItem(chunk_id=chunk_id, citation_label="[^1]", ticker="AAPL", fiscal_year=2023)],
        has_sufficient_evidence=True,
    )
    mock_agent_result = MagicMock()
    mock_agent_result.output = answer
    mock_agent.run = AsyncMock(return_value=mock_agent_result)

    # User asks follow-up with no company name: "How does that compare to 2023?"
    async for _ in stream_orchestrated_turn(
        client=mock_client,
        thread_id=thread_id,
        user_content="How does that compare to 2023?",
        retriever=mock_retriever,
        agent_override=mock_agent,
    ):
        pass

    # Verify retriever inherited AAPL ticker
    call_kwargs = mock_retriever.retrieve.call_args.kwargs
    assert call_kwargs["ticker"] == "AAPL"
    # Verify agent.run received conversation history
    run_call_kwargs = mock_agent.run.call_args.kwargs
    assert "Apple revenue was $391,035M" in run_call_kwargs["deps"].conversation_history


@pytest.mark.anyio
async def test_stream_educational_concept_query() -> None:
    """Verifies that general educational finance concepts stream correctly without requiring citations."""
    thread_id = uuid.uuid4()

    mock_client = MagicMock()
    mock_client.table().select().eq().order().execute.return_value = MagicMock(data=[])
    mock_user_msg = {"id": str(uuid.uuid4())}
    mock_asst_msg = {"id": str(uuid.uuid4())}
    mock_client.table().insert().execute.side_effect = [
        MagicMock(data=[mock_user_msg]),
        MagicMock(data=[mock_asst_msg]),
    ]

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = []

    mock_agent = MagicMock()
    concept_answer = GroundedAnswer(
        answer=(
            "**Capital budgeting** is the corporate planning process used to evaluate long-term capital investments. "
            "In SEC 10-K filings, these appear under Capital Expenditures in the Statement of Cash Flows. "
            "Would you like to examine CapEx disclosures for Apple, Amazon, Alphabet, Microsoft, or NVIDIA?"
        ),
        citations=[],
        has_sufficient_evidence=True,
        refusal_reason=None,
    )
    mock_agent_result = MagicMock()
    mock_agent_result.output = concept_answer
    mock_agent.run = AsyncMock(return_value=mock_agent_result)

    chunks = []
    async for s in stream_orchestrated_turn(
        client=mock_client,
        thread_id=thread_id,
        user_content="What is capital budgeting?",
        retriever=mock_retriever,
        agent_override=mock_agent,
    ):
        chunks.append(s)

    full_stream = "".join(chunks)
    assert '0:"**Capital' in full_stream
    assert '0:"Capital ' in full_stream and '0:"Expenditures ' in full_stream
    assert 'd:{"finishReason": "stop"' in full_stream
    # No citations data part should be emitted when citations list is empty
    assert '2:[{"type": "citations"' not in full_stream


@pytest.mark.anyio
async def test_stream_non_financial_query_refusal() -> None:
    """Verifies that non-financial out-of-domain queries stream the specialization refusal without error."""
    thread_id = uuid.uuid4()

    mock_client = MagicMock()
    mock_client.table().select().eq().order().execute.return_value = MagicMock(data=[])
    mock_user_msg = {"id": str(uuid.uuid4())}
    mock_asst_msg = {"id": str(uuid.uuid4())}
    mock_client.table().insert().execute.side_effect = [
        MagicMock(data=[mock_user_msg]),
        MagicMock(data=[mock_asst_msg]),
    ]

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = []

    mock_agent = MagicMock()
    refusal_answer = GroundedAnswer(
        answer=(
            "As Meridian Research's Document Assistant, I specialize exclusively in institutional equity research, "
            "SEC 10-K filing analysis, and corporate finance/accounting concepts. I cannot assist with non-financial topics "
            "such as psychology. Please feel free to ask questions regarding corporate finance or SEC 10-K disclosures "
            "for our coverage universe (AAPL, AMZN, GOOGL, MSFT, and NVDA)."
        ),
        citations=[],
        has_sufficient_evidence=False,
        refusal_reason="Out of domain: non-financial topic",
    )
    mock_agent_result = MagicMock()
    mock_agent_result.output = refusal_answer
    mock_agent.run = AsyncMock(return_value=mock_agent_result)

    chunks = []
    async for s in stream_orchestrated_turn(
        client=mock_client,
        thread_id=thread_id,
        user_content="What are the stages of psychological grief?",
        retriever=mock_retriever,
        agent_override=mock_agent,
    ):
        chunks.append(s)

    full_stream = "".join(chunks)
    assert '0:"As ' in full_stream or '0:"As' in full_stream
    assert "psychology" in full_stream
    assert 'd:{"finishReason": "stop"' in full_stream
    assert '2:[{"type": "citations"' not in full_stream


@pytest.mark.anyio
async def test_maybe_generate_thread_title_deferred_for_greetings() -> None:
    """Verifies that greetings defer titling, while real financial inquiries auto-name the thread."""
    from app.chat.orchestrator import _is_low_information_greeting, maybe_generate_thread_title

    # 1. Unit check for greeting detector
    assert _is_low_information_greeting("hi") is True
    assert _is_low_information_greeting("hi bud") is True
    assert _is_low_information_greeting("hey bro") is True
    assert _is_low_information_greeting("hi how are you") is True
    assert _is_low_information_greeting("Hello there!") is True
    assert _is_low_information_greeting("good morning") is True
    assert _is_low_information_greeting("ok leave it i have to sleep") is True
    assert _is_low_information_greeting("What was Microsoft Azure revenue in FY24?") is False
    assert _is_low_information_greeting("is it renaissance or rennaissance?") is False

    thread_id = uuid.uuid4()
    mock_client = MagicMock()

    # 2. When user sends "hi how are you" in an untitled thread -> deferred (returns None)
    mock_client.table().select().eq().execute.return_value = MagicMock(
        data=[{"id": str(thread_id), "title": "Untitled Analysis"}]
    )
    title_res = await maybe_generate_thread_title(
        client=mock_client,
        thread_id=thread_id,
        user_content="hi how are you",
    )
    assert title_res is None

    # 3. When thread already has a good title ("Apple iPhone Sales") -> returns None (does not overwrite)
    mock_client.table().select().eq().execute.return_value = MagicMock(
        data=[{"id": str(thread_id), "title": "Apple FY24 iPhone Sales"}]
    )
    title_res_locked = await maybe_generate_thread_title(
        client=mock_client,
        thread_id=thread_id,
        user_content="What were Google TAC expenses in 2024?",
    )
    assert title_res_locked is None


# ===========================================================================
# ROUTING, BROADENED FINANCE COVERAGE, & TICKER INHERITANCE TRANSITION TESTS
# ===========================================================================

def test_all_15_benchmark_queries_select_covered_filing_rag_route() -> None:
    """Regression Gate: All 15 retrieval benchmark queries MUST strictly select the covered-filing RAG path."""
    import sys
    from pathlib import Path
    from app.chat.orchestrator import _classify_query_intent

    # Import BENCHMARK_QUERIES dynamically
    scripts_path = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts_path) not in sys.path:
        sys.path.insert(0, str(scripts_path))
    from run_eval_benchmark import BENCHMARK_QUERIES

    assert len(BENCHMARK_QUERIES) == 15, "Expected 15 benchmark queries"

    for eq in BENCHMARK_QUERIES:
        intent = _classify_query_intent(eq.query, [])
        assert intent == "sec_filing_rag", (
            f"Benchmark query Q{eq.id} '{eq.query}' failed to select 'sec_filing_rag' route! Got: '{intent}'"
        )


def test_6_gate_query_classification_matrix() -> None:
    """Verifies that the 6-gate routing classifier accurately partitions queries without regression."""
    from app.chat.orchestrator import _classify_query_intent

    prior_apple = [{"role": "user", "content": "What was Apple revenue in 2024?"}]

    # Gate 1: Trading advice refusal
    assert _classify_query_intent("Should I buy NVDA?", []) == "trading_advice_refusal"
    assert _classify_query_intent("What is your price target for Apple stock?", []) == "trading_advice_refusal"

    # Gate 2: Unindexed issuer boundary
    assert _classify_query_intent("What was Tesla's FY2024 gross margin?", []) == "unindexed_issuer_refusal"
    assert _classify_query_intent("Summarize Netflix's 10-K", []) == "unindexed_issuer_refusal"

    # Gate 3: Covered issuer filing questions (explicit, comparative, and mixed)
    assert _classify_query_intent("What was Apple's Services revenue in its FY2024 10-K?", []) == "sec_filing_rag"
    assert _classify_query_intent("Compare Microsoft and Amazon's reported results", []) == "sec_filing_rag"
    assert _classify_query_intent("How did inflation affect Microsoft's reported margins, and what is inflation?", []) == "sec_filing_rag"
    assert _classify_query_intent("Services revenue?", []) == "sec_filing_rag"

    # Gate 4: Analyst utilities & greetings
    assert _classify_query_intent("How do I calculate XIRR in Excel?", []) == "analyst_utility"
    assert _classify_query_intent("is it renaissance or rennaissance?", []) == "analyst_utility"
    assert _classify_query_intent("convert 75 bps to percentage", []) == "analyst_utility"
    assert _classify_query_intent("hi how are you", []) == "greeting_lifecycle"
    assert _classify_query_intent("all good", []) == "greeting_lifecycle"
    assert _classify_query_intent("bye", []) == "greeting_lifecycle"

    # Gate 5: Substantive General Finance & Financial History
    assert _classify_query_intent("What caused the 2008 financial crisis, and how did political decisions affect the response?", []) == "general_finance"
    assert _classify_query_intent("Explain the Enron accounting scandal", []) == "general_finance"
    assert _classify_query_intent("What caused the 1987 market crash?", []) == "general_finance"
    assert _classify_query_intent("Explain Dodd-Frank Wall Street Reform Act", []) == "general_finance"
    assert _classify_query_intent("What is capital budgeting?", []) == "general_finance"

    # Ticker inheritance separation test:
    # After an Apple conversation, filing follow-up inherits ticker, but general finance DOES NOT!
    assert _classify_query_intent("How did that compare with 2023?", prior_apple) == "sec_filing_rag_inherited"
    assert _classify_query_intent("What about their operating margins?", prior_apple) == "sec_filing_rag_inherited"
    assert _classify_query_intent("What caused the 2008 financial crisis, and how did political decisions affect the response?", prior_apple) == "general_finance"
    assert _classify_query_intent("Explain the Enron accounting scandal", prior_apple) == "general_finance"

    # Gate 6: Genuinely out-of-domain
    assert _classify_query_intent("Who was the first emperor of Rome?", []) == "out_of_domain_refusal"
    assert _classify_query_intent("How do I bake chocolate chip cookies?", []) == "out_of_domain_refusal"


@pytest.mark.anyio
async def test_clean_transition_from_company_to_general_finance() -> None:
    """Verifies that asking about the 2008 crisis after discussing Apple does NOT inherit AAPL ticker or pollute retrieval."""
    thread_id = uuid.uuid4()

    mock_client = MagicMock()
    # Prior thread history: Turn 1 was about Apple (AAPL)
    prev_user = {"role": "user", "content": "What was Apple revenue in 2024?"}
    prev_asst = {"role": "assistant", "content": "Apple revenue was $391,035M [^1]."}
    mock_client.table().select().eq().order().execute.return_value = MagicMock(
        data=[prev_user, prev_asst]
    )
    mock_client.table().insert().execute.side_effect = [
        MagicMock(data=[{"id": str(uuid.uuid4())}]),
        MagicMock(data=[{"id": str(uuid.uuid4())}]),
    ]

    mock_retriever = MagicMock()

    mock_agent = MagicMock()
    crisis_answer = GroundedAnswer(
        answer=(
            "The **2008 Global Financial Crisis** was precipitated by the collapse of the U.S. subprime housing market, "
            "widespread securitization of high-risk mortgages into Collateralized Debt Obligations (CDOs), and extreme leverage. "
            "Political and regulatory decisions shaped the response through the Troubled Asset Relief Program (TARP), "
            "emergency Federal Reserve liquidity facilities, and the subsequent passage of the Dodd-Frank Act."
        ),
        citations=[],
        has_sufficient_evidence=True,
        refusal_reason=None,
    )
    mock_agent_result = MagicMock()
    mock_agent_result.output = crisis_answer
    mock_agent.run = AsyncMock(return_value=mock_agent_result)

    chunks = []
    async for s in stream_orchestrated_turn(
        client=mock_client,
        thread_id=thread_id,
        user_content="What caused the 2008 financial crisis, and how did political decisions affect the response?",
        retriever=mock_retriever,
        agent_override=mock_agent,
    ):
        chunks.append(s)

    full_stream = "".join(chunks)

    # 1. Retriever should NOT have been called with AAPL!
    assert mock_retriever.retrieve.call_count == 0, "Retriever should not be called for general finance questions"

    # 2. Status message should transparently state Institutional Financial Synthesis (not 10-K hybrid retrieval)
    assert "Institutional Financial Synthesis" in full_stream
    assert "Concurrent Hybrid Retrieval" not in full_stream

    # 3. Stream should finish cleanly without citations event
    assert '2:[{"type": "citations"' not in full_stream
    assert 'd:{"finishReason": "stop"' in full_stream
    assert '0:"Troubled ' in full_stream and '0:"(TARP)' in full_stream


@pytest.mark.anyio
async def test_stream_mixed_query_microsoft_and_inflation() -> None:
    """Verifies that mixed inquiries (Microsoft margins + inflation concept) route to 10-K RAG, cite Microsoft disclosures, and explain inflation."""
    thread_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    p = RetrievedPassage(
        chunk_id=chunk_id,
        document_id=uuid.uuid4(),
        ticker="MSFT",
        company_name="Microsoft Corporation",
        fiscal_year=2024,
        filing_type="10-K",
        filing_date="2024-07-30",
        chunk_index=1,
        text="Operating income was $109,433 million for fiscal year 2024.",
        full_context_text="Operating income was $109,433 million for fiscal year 2024.",
        rrf_score=0.032,
        citation_source="Microsoft Corporation (MSFT) FY2024 10-K [Item 7. MD&A]",
    )

    mock_client = MagicMock()
    mock_client.table().select().eq().order().execute.return_value = MagicMock(data=[])
    mock_client.table().insert().execute.side_effect = [
        MagicMock(data=[{"id": str(uuid.uuid4())}]),
        MagicMock(data=[{"id": str(uuid.uuid4())}]),
        MagicMock(data=[{"id": str(uuid.uuid4()), "chunk_id": str(chunk_id)}]),
    ]

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = [p]

    mock_agent = MagicMock()
    mixed_answer = GroundedAnswer(
        answer=(
            "In fiscal year 2024, Microsoft reported operating income of $109,433 million [^1], expanding operating margins. "
            "Inflation is the macroeconomic rate at which the general level of prices for goods and services rises, eroding purchasing power."
        ),
        citations=[
            CitationItem(
                chunk_id=chunk_id,
                citation_label="[^1]",
                ticker="MSFT",
                fiscal_year=2024,
                snippet="$109,433 million",
            )
        ],
        has_sufficient_evidence=True,
    )
    mock_agent_result = MagicMock()
    mock_agent_result.output = mixed_answer
    mock_agent.run = AsyncMock(return_value=mock_agent_result)

    chunks = []
    async for s in stream_orchestrated_turn(
        client=mock_client,
        thread_id=thread_id,
        user_content="How did inflation affect Microsoft's reported margins, and what is inflation?",
        retriever=mock_retriever,
        agent_override=mock_agent,
    ):
        chunks.append(s)

    full_stream = "".join(chunks)

    # 1. Filing retrieval was triggered for MSFT
    assert mock_retriever.retrieve.call_count == 1
    call_kwargs = mock_retriever.retrieve.call_args.kwargs
    assert call_kwargs["ticker"] == "MSFT"

    # 2. Status message should show 4-Gate Grounding
    assert "4-Gate Fail-Closed Grounding Verification" in full_stream

    # 3. Verified citation for Microsoft should be streamed
    assert '2:[{"type": "citations"' in full_stream
    assert "MSFT" in full_stream
    assert 'd:{"finishReason": "stop"' in full_stream
