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
