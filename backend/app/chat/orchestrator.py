"""Turn orchestrator coordinating retrieval, agent generation, validation, and persistence."""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from supabase import Client

from app.assistant.agent import DocumentAgentDeps, create_document_agent
from app.assistant.schemas import GroundedAnswer
from app.chat.streaming import format_ai_sdk_finish_part, format_ai_sdk_text_part
from app.database.chats import save_citations, save_message
from app.grounding.validator import GroundingValidator, ValidationResult
from app.retrieval.models import RetrievedPassage
from app.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)


@dataclass
class TurnResult:
    """Complete result of an orchestrated conversation turn."""

    user_message_id: uuid.UUID
    assistant_message_id: uuid.UUID
    answer: GroundedAnswer
    validation: ValidationResult
    citations_saved: list[dict[str, Any]]
    passages_used: list[RetrievedPassage]


def _extract_ticker_and_fy(query: str) -> tuple[str | None, int | None]:
    """Lightweight heuristic to detect company ticker and fiscal year in user queries."""
    query_upper = query.upper()
    ticker = None
    if "AAPL" in query_upper or "APPLE" in query_upper:
        ticker = "AAPL"
    elif "NVDA" in query_upper or "NVIDIA" in query_upper:
        ticker = "NVDA"
    elif "MSFT" in query_upper or "MICROSOFT" in query_upper:
        ticker = "MSFT"
    elif "AMZN" in query_upper or "AMAZON" in query_upper:
        ticker = "AMZN"
    elif (
        "GOOGL" in query_upper
        or "GOOG" in query_upper
        or "ALPHABET" in query_upper
        or "GOOGLE" in query_upper
    ):
        ticker = "GOOGL"

    import re

    match = re.search(r"\b(202[0-5])\b", query)
    fiscal_year = int(match.group(1)) if match else None

    return ticker, fiscal_year


async def orchestrate_turn(
    client: Client,
    thread_id: uuid.UUID,
    user_content: str,
    retriever: Retriever | None = None,
    validator: GroundingValidator | None = None,
    agent_override: Any | None = None,
    user_metadata: dict[str, Any] | None = None,
) -> TurnResult:
    """Execute a single complete turn synchronously with database persistence."""
    retriever = retriever or Retriever()
    validator = validator or GroundingValidator(strict=True)
    agent = agent_override or create_document_agent()

    # 1. Persist user message
    user_msg = save_message(
        client=client,
        thread_id=thread_id,
        role="user",
        content=user_content,
        ai_sdk_metadata=user_metadata,
    )
    user_msg_id = uuid.UUID(str(user_msg["id"]))

    # 2. Extract heuristics and run Phase 5 hybrid retrieval
    ticker, fiscal_year = _extract_ticker_and_fy(user_content)
    logger.info(
        "Executing retrieval: query='%s', ticker=%s, fy=%s",
        user_content,
        ticker,
        fiscal_year,
    )
    initial_passages = retriever.retrieve(
        query=user_content,
        ticker=ticker,
        fiscal_year=fiscal_year,
        top_n=5,
        expand_neighbors=True,
    )

    deps = DocumentAgentDeps(
        retriever=retriever,
        initial_passages=initial_passages,
    )

    # 3. Run PydanticAI Gemini agent
    agent_result = await agent.run(user_content, deps=deps)
    grounded_answer: GroundedAnswer = agent_result.output

    # 4. Enforce grounding verification
    val_result: ValidationResult = validator.validate(
        answer=grounded_answer,
        retrieved_passages=deps.all_retrieved_passages,
    )

    # If strict validation failed, append warning notice to the analyst
    final_answer_text = grounded_answer.answer
    if not val_result.is_valid:
        warning_msg = (
            "\n\n> [!WARNING]\n"
            "> **Grounding Verification Alert**: Some citations in this response could not be verified "
            "against the ingested corpus. Unverified claims have been flagged."
        )
        final_answer_text += warning_msg

    # 5. Persist assistant message
    asst_msg = save_message(
        client=client,
        thread_id=thread_id,
        role="assistant",
        content=final_answer_text,
    )
    asst_msg_id = uuid.UUID(str(asst_msg["id"]))

    # 6. Persist citations in message_citations
    citation_payloads: list[dict[str, Any]] = []
    passage_by_id = {p.chunk_id: p for p in deps.all_retrieved_passages}

    for idx, cit in enumerate(val_result.verified_citations, start=1):
        p = passage_by_id.get(cit.chunk_id)
        citation_payloads.append(
            {
                "chunk_id": cit.chunk_id,
                "citation_index": idx,
                "ticker": cit.ticker or (p.ticker if p else None),
                "filing_type": p.filing_type if p else "10-K",
                "filing_date": p.filing_date if p else None,
                "section": cit.section
                or (" > ".join(p.headings) if p and p.headings else None),
                "snippet": cit.snippet or (p.text[:200] if p else None),
            }
        )

    saved_citations = save_citations(client, asst_msg_id, citation_payloads)

    return TurnResult(
        user_message_id=user_msg_id,
        assistant_message_id=asst_msg_id,
        answer=grounded_answer,
        validation=val_result,
        citations_saved=saved_citations,
        passages_used=deps.all_retrieved_passages,
    )


async def stream_orchestrated_turn(
    client: Client,
    thread_id: uuid.UUID,
    user_content: str,
    retriever: Retriever | None = None,
    validator: GroundingValidator | None = None,
    agent_override: Any | None = None,
    user_metadata: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    """Execute turn and stream SSE events (AI SDK format) to the frontend client."""
    # Execute turn orchestration
    result = await orchestrate_turn(
        client=client,
        thread_id=thread_id,
        user_content=user_content,
        retriever=retriever,
        validator=validator,
        agent_override=agent_override,
        user_metadata=user_metadata,
    )

    # 1. Stream the text response in token chunks
    words = result.answer.answer.split(" ")
    for i, word in enumerate(words):
        chunk = word + (" " if i < len(words) - 1 else "")
        yield format_ai_sdk_text_part(chunk)
        await asyncio.sleep(0.01)

    # 2. Yield citation metadata part for the UI
    if result.citations_saved:
        citation_data = {
            "type": "citations",
            "messageId": str(result.assistant_message_id),
            "citations": result.citations_saved,
        }
        # Format as AI SDK data part (prefix 2:)
        yield f"2:[{json.dumps(citation_data)}]\n"

    # 3. Finish stream
    yield format_ai_sdk_finish_part()
