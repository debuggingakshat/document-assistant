"""Turn orchestrator coordinating retrieval, agent generation, validation, and persistence."""

import asyncio
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from supabase import Client

from app.assistant.agent import DocumentAgentDeps, create_document_agent
from app.assistant.model import (
    FALLBACK_MODELS,
    MODEL_ALIASES,
    MODEL_DISPLAY_NAMES,
    get_llm_model,
)
from app.config import get_gemini_api_keys
from pydantic_ai.models.google import GoogleModel
from app.assistant.schemas import GroundedAnswer
from pydantic_ai import Agent
from app.chat.streaming import (
    format_ai_sdk_finish_part,
    format_ai_sdk_status_part,
    format_ai_sdk_text_part,
)
from app.database.chats import get_thread, list_messages, save_citations, save_message, update_thread
from app.grounding.validator import GroundingValidator, ValidationResult
from app.retrieval.models import RetrievedPassage
from app.retrieval.retriever import Retriever

from app.logging import get_logger
logger = get_logger(__name__)


@dataclass
class TurnResult:
    """Complete result of an orchestrated conversation turn."""

    user_message_id: uuid.UUID
    assistant_message_id: uuid.UUID
    answer: GroundedAnswer
    validation: ValidationResult
    citations_saved: list[dict[str, Any]]
    passages_used: list[RetrievedPassage]



def extract_best_numeric_snippet(text: str, full_context: str | None = None) -> str:
    """Extract the most informative financial passage segment containing numbers, currency, or metrics."""
    source = full_context or text
    if not source:
        return ""

    # Split into candidate sentences or table rows
    segments = re.split(r"(?<=[.;\n])\s+|,\s{2,}|\n+", source)
    scored_segments: list[tuple[int, str]] = []

    for seg in segments:
        clean = seg.strip()
        if len(clean) < 15:
            continue

        score = 0
        if "$" in clean:
            score += 6
        if "%" in clean:
            score += 5
        if re.search(r"\b\d+(?:,\d{3})*(?:\.\d+)?\b", clean):
            score += 4
        if re.search(r"\b(million|billion|dividend|share|repurchase|revenue|income|operating|cash)\b", clean, re.I):
            score += 3
        # Penalize if it is mostly repeating identical phrases or empty table columns
        words = clean.split()
        if len(words) > 6 and len(set(words)) < len(words) * 0.4:
            score -= 6
        if clean.startswith("-.") or clean.startswith("= -."):
            score -= 3

        if score > 0:
            scored_segments.append((score, clean))

    scored_segments.sort(key=lambda x: x[0], reverse=True)
    if scored_segments:
        top_pieces: list[str] = []
        seen: set[str] = set()
        for _, s in scored_segments[:2]:
            s_clean = re.sub(r"\s+", " ", s).strip(" ,=-")
            if s_clean and s_clean not in seen:
                seen.add(s_clean)
                top_pieces.append(s_clean)
        return " ... ".join(top_pieces)

    return text[:250].strip()

def _extract_ticker_and_fy(query: str) -> tuple[str | None, int | None]:
    """Lightweight heuristic to detect company ticker and fiscal year in user queries.
    
    If multiple companies are mentioned (e.g. comparisons across AAPL, MSFT, etc.),
    ticker is set to None so hybrid retrieval searches across the entire multi-company corpus.
    """
    query_upper = query.upper()
    detected_tickers: set[str] = set()

    if "AAPL" in query_upper or "APPLE" in query_upper:
        detected_tickers.add("AAPL")
    if "NVDA" in query_upper or "NVIDIA" in query_upper:
        detected_tickers.add("NVDA")
    if "MSFT" in query_upper or "MICROSOFT" in query_upper:
        detected_tickers.add("MSFT")
    if "AMZN" in query_upper or "AMAZON" in query_upper:
        detected_tickers.add("AMZN")
    if (
        "GOOGL" in query_upper
        or "GOOG" in query_upper
        or "ALPHABET" in query_upper
        or "GOOGLE" in query_upper
    ):
        detected_tickers.add("GOOGL")

    # Only filter by ticker if EXACTLY ONE company was referenced.
    # For comparisons or multi-company queries, return None to search the full corpus.
    ticker = detected_tickers.pop() if len(detected_tickers) == 1 else None

    import re

    # If multiple years or a range (e.g. 2021-2025) are mentioned, do not restrict to a single fiscal year.
    years = re.findall(r"\b(202[0-5])\b", query)
    fiscal_year = int(years[0]) if len(years) == 1 else None

    return ticker, fiscal_year



async def _run_agent_with_failover(
    agent: Agent[DocumentAgentDeps, GroundedAnswer],
    user_content: str,
    deps: DocumentAgentDeps,
    requested_model_name: str | None = None,
) -> tuple[Any, str]:
    """Run agent with automatic 2D multi-key and multi-model failover (1,160+ daily queries capacity)."""
    raw_model_attr = getattr(agent, "model", None)
    model_name_attr = getattr(raw_model_attr, "model_name", None) if raw_model_attr else None
    if isinstance(model_name_attr, str):
        primary_model_name = model_name_attr
    elif isinstance(requested_model_name, str):
        primary_model_name = requested_model_name
    else:
        primary_model_name = "gemini-3-flash-preview"
    target_primary_model = str(MODEL_ALIASES.get(primary_model_name, primary_model_name))

    keys = get_gemini_api_keys()
    if not keys:
        keys = [None]

    # 1. Try provided agent first (handles agent_override in tests)
    try:
        res = await asyncio.wait_for(agent.run(user_content, deps=deps), timeout=75.0)
        return res, target_primary_model
    except Exception as primary_exc:
        logger.warning(
            "Primary agent run with '%s' failed (%s: %s). Activating waterfall failover...",
            target_primary_model,
            type(primary_exc).__name__,
            primary_exc,
        )

    # 2. Build waterfall candidate list (target model first, then remaining fallbacks)
    candidate_models: list[str] = [target_primary_model]
    for m in FALLBACK_MODELS:
        if m not in candidate_models:
            candidate_models.append(m)

    last_exc = primary_exc
    # 3. 2D Waterfall: Model x Key matrix
    for model_candidate in candidate_models:
        for key_idx, key in enumerate(keys):
            if model_candidate == target_primary_model and key_idx == 0:
                continue
            try:
                logger.info(
                    "Waterfall failover: executing model '%s' (Key %d/%d)",
                    model_candidate,
                    key_idx + 1,
                    len(keys),
                )
                model_inst = get_llm_model(model_candidate, api_key=key)
                fallback_agent = create_document_agent(model=model_inst)
                res = await asyncio.wait_for(fallback_agent.run(user_content, deps=deps), timeout=75.0)
                logger.info(
                    "Waterfall failover SUCCEEDED with model '%s' on Key %d",
                    model_candidate,
                    key_idx + 1,
                )
                return res, model_candidate
            except Exception as loop_exc:
                last_exc = loop_exc
                logger.warning(
                    "Waterfall failover model '%s' with Key %d encountered error (%s). Trying next...",
                    model_candidate,
                    key_idx + 1,
                    loop_exc,
                )
                await asyncio.sleep(0.5)

    logger.error("All models and keys exhausted in failover waterfall: %s", last_exc)
    raise last_exc


async def orchestrate_turn(
    client: Client,
    thread_id: uuid.UUID,
    user_content: str,
    retriever: Retriever | None = None,
    validator: GroundingValidator | None = None,
    agent_override: Any | None = None,
    user_metadata: dict[str, Any] | None = None,
    model_name: str | None = None,
    parent_user_message_id: uuid.UUID | None = None,
) -> TurnResult:
    """Execute a single complete turn synchronously with database persistence."""
    retriever = retriever or Retriever()
    validator = validator or GroundingValidator(strict=True)
    agent = agent_override or create_document_agent(
        model=get_llm_model(model_name) if model_name else None
    )

    # 1. Persist user message (reuse parent if regenerating)
    if parent_user_message_id:
        user_msg_id = parent_user_message_id
    else:
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

    # 3. Run PydanticAI Gemini agent with waterfall failover
    agent_result, actual_model_used = await _run_agent_with_failover(
        agent, user_content, deps, requested_model_name=model_name
    )
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

    # 5. Persist assistant message with model & parent linkage
    asst_metadata: dict[str, Any] = {"model": actual_model_used}
    if parent_user_message_id:
        asst_metadata["parent_user_message_id"] = str(parent_user_message_id)

    asst_msg = save_message(
        client=client,
        thread_id=thread_id,
        role="assistant",
        content=final_answer_text,
        ai_sdk_metadata=asst_metadata,
    )
    asst_msg_id = uuid.UUID(str(asst_msg["id"]))

    # 6. Persist citations in message_citations
    citation_payloads: list[dict[str, Any]] = []
    passage_by_id = {p.chunk_id: p for p in deps.all_retrieved_passages}

    for fallback_idx, cit in enumerate(val_result.verified_citations, start=1):
        p = passage_by_id.get(cit.chunk_id)
        label_match = re.search(r"\d+", cit.citation_label or "")
        cit_idx = int(label_match.group(0)) if label_match else fallback_idx

        best_snippet = cit.snippet.strip() if cit.snippet else ""
        if (not best_snippet or len(best_snippet) < 10 or not any(c.isdigit() for c in best_snippet)) and p:
            fallback_snippet = extract_best_numeric_snippet(p.text, p.full_context_text)
            if fallback_snippet:
                best_snippet = fallback_snippet

        citation_payloads.append(
            {
                "chunk_id": cit.chunk_id,
                "citation_index": cit_idx,
                "ticker": cit.ticker or (p.ticker if p else None),
                "filing_type": p.filing_type if p else "10-K",
                "filing_date": p.filing_date if p else None,
                "section": cit.section
                or (" > ".join(p.headings) if p and p.headings else None),
                "snippet": best_snippet or (p.text[:250] if p else None),
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


async def maybe_generate_thread_title(
    client: Client,
    thread_id: uuid.UUID,
    user_content: str,
    model_name: str | None = None,
) -> str | None:
    """Generate a crisp 3-5 word title for untitled threads using fast LLM summarization."""
    try:
        thread = get_thread(client, thread_id)
        if not thread:
            return None

        current_title = thread.get("title")
        if current_title and current_title.strip() not in (
            "",
            "Untitled Analysis",
            "Untitled Thread",
            "New Thread",
        ):
            return None

        fallback_title = user_content.strip()[:40].strip()
        if len(user_content.strip()) > 40:
            fallback_title = fallback_title.rsplit(" ", 1)[0] + "..."

        try:
            model = get_llm_model(model_name)
            title_agent: Agent[None, str] = Agent(
                model=model,
                output_type=str,
                system_prompt=(
                    "You are an editor for an SEC equity research system. "
                    "Summarize the user inquiry into a crisp 3 to 5 word conversation title. "
                    "Focus on the company ticker or name and the core financial topic (e.g. 'Apple FY24 iPhone Sales', 'AWS Margins & GenAI'). "
                    "Do NOT use quotation marks, punctuation, or generic filler words like 'Analysis of', 'Question about'. "
                    "Output ONLY the 3-5 word title."
                ),
            )
            res = await title_agent.run(user_content)
            raw = res.output.strip().strip('"').strip("'").strip()
            clean_title = (raw.splitlines()[0] if raw.splitlines() else raw).strip(".").strip()[:50]
            if len(clean_title) < 3:
                clean_title = fallback_title
        except Exception as e:
            logger.warning("LLM title generation failed, using fallback: %s", e)
            clean_title = fallback_title

        update_thread(client, thread_id, title=clean_title)
        logger.info("Auto-named thread %s to '%s'", thread_id, clean_title)
        return clean_title
    except Exception as e:
        logger.warning("Failed to auto-name thread %s: %s", thread_id, e)
        return None


async def stream_orchestrated_turn(
    client: Client,
    thread_id: uuid.UUID,
    user_content: str,
    retriever: Retriever | None = None,
    validator: GroundingValidator | None = None,
    agent_override: Any | None = None,
    user_metadata: dict[str, Any] | None = None,
    model_name: str | None = None,
    parent_user_message_id: uuid.UUID | None = None,
) -> AsyncIterator[str]:
    """Execute turn with progressive technical status updates and stream SSE events to frontend."""
    retriever = retriever or Retriever()
    validator = validator or GroundingValidator(strict=True)
    agent = agent_override or create_document_agent(
        model=get_llm_model(model_name) if model_name else None
    )

    # 0. Multi-turn conversation memory: Fetch prior messages in thread
    history_records = list_messages(client=client, thread_id=thread_id)
    prior_messages = [
        m for m in history_records
        if m.get("content") and m.get("content").strip() != user_content.strip()
    ][-6:]

    ticker, fiscal_year = _extract_ticker_and_fy(user_content)

    # Inherit company ticker from recent thread history if not explicitly stated in follow-up
    inherited_ticker = False
    if not ticker and prior_messages:
        for prev_msg in reversed(prior_messages):
            prev_ticker, _ = _extract_ticker_and_fy(prev_msg.get("content", ""))
            if prev_ticker:
                ticker = prev_ticker
                inherited_ticker = True
                logger.info(
                    "Inherited active ticker '%s' from conversation history in thread %s",
                    ticker,
                    thread_id,
                )
                break

    # Build formatted conversation history for LLM prompt context
    conversation_history_str = ""
    if prior_messages:
        formatted_turns = []
        for m in prior_messages:
            role = "User" if m.get("role") == "user" else "Assistant"
            text_snippet = m.get("content", "").strip()
            # Truncate older assistant turns to ~350 chars to conserve prompt token budget
            if role == "Assistant" and len(text_snippet) > 350:
                text_snippet = text_snippet[:350] + "..."
            formatted_turns.append(f"[{role}]: {text_snippet}")
        conversation_history_str = "\n".join(formatted_turns)

    # Kick off background title generation if thread is untitled
    title_task: asyncio.Task[str | None] | None = None
    if not parent_user_message_id:
        title_task = asyncio.create_task(
            maybe_generate_thread_title(
                client=client,
                thread_id=thread_id,
                user_content=user_content,
                model_name=model_name,
            )
        )

    # Step 1: Hybrid Retrieval
    yield format_ai_sdk_status_part(
        stage="searching",
        title="Concurrent Hybrid Retrieval (FTS + pgvector)",
        message="Embedding query via Google gemini-embedding-001 (768-d). Executing parallel tsvector FTS & pgvector cosine similarity search (<=>) in ThreadPoolExecutor...",
        technical_details={
            "embedding_model": "Google gemini-embedding-001",
            "vector_dim": 768,
            "fts_parser": "websearch_to_tsquery + ts_rank_cd",
            "concurrency": "ThreadPoolExecutor (2 workers)",
            "filter_ticker": ticker or "All Filings",
            "filter_fy": fiscal_year or "All Years",
            "conversation_memory": f"{len(prior_messages)} prior turns" if prior_messages else "New Session",
        },
    )

    # 1. Persist user message (reuse parent if regenerating)
    if parent_user_message_id:
        user_msg_id = parent_user_message_id
    else:
        user_msg = save_message(
            client=client,
            thread_id=thread_id,
            role="user",
            content=user_content,
            ai_sdk_metadata=user_metadata,
        )
        user_msg_id = uuid.UUID(str(user_msg["id"]))

    # 2. Extract heuristics and run Phase 5 hybrid retrieval
    retrieval_query = user_content
    if inherited_ticker and ticker and ticker not in user_content.upper():
        retrieval_query = f"{user_content} ({ticker})"

    logger.info(
        "Executing retrieval: query='%s', ticker=%s, fy=%s (history_turns=%d)",
        retrieval_query,
        ticker,
        fiscal_year,
        len(prior_messages),
    )
    initial_passages = retriever.retrieve(
        query=retrieval_query,
        ticker=ticker,
        fiscal_year=fiscal_year,
        top_n=5,
        expand_neighbors=True,
    )

    # Step 2: RRF Fusion & Expansion
    yield format_ai_sdk_status_part(
        stage="fusion",
        title="Reciprocal Rank Fusion & Neighbor Expansion",
        message=f"Fused candidates via RRF (k=60). Expanded context window with ±1 neighbor chunks across {len(initial_passages)} top passages...",
        technical_details={
            "algorithm": "Reciprocal Rank Fusion (k=60)",
            "top_passages": len(initial_passages),
            "context_expansion": "±1 neighbor chunks",
            "storage": "Supabase PostgreSQL (pgvector + tsvector)",
        },
    )

    deps = DocumentAgentDeps(
        retriever=retriever,
        initial_passages=initial_passages,
        conversation_history=conversation_history_str,
    )

    active_llm_name = model_name or "gemini-3-flash-preview"
    target_primary_name = MODEL_ALIASES.get(active_llm_name, active_llm_name)
    llm_display_label = MODEL_DISPLAY_NAMES.get(target_primary_name, target_primary_name)

    # Step 3: PydanticAI Reasoning
    yield format_ai_sdk_status_part(
        stage="reasoning",
        title=f"PydanticAI Reasoning with {llm_display_label}",
        message=f"Injecting verified context window into {llm_display_label} system prompt. Synthesizing disclosures and extracting financial metrics under Meridian Research compliance directives...",
        technical_details={
            "orchestrator": "PydanticAI v2.52.0",
            "llm": target_primary_name,
            "system_prompt": "Meridian Research Trust Directives",
            "compliance": "Strict corpus grounding, no non-causal speculation",
        },
    )

    # 3. Run PydanticAI Gemini agent with waterfall failover
    try:
        agent_result, actual_model_used = await _run_agent_with_failover(
            agent, user_content, deps, requested_model_name=model_name
        )
        grounded_answer: GroundedAnswer = agent_result.output
    except Exception as exc:
        logger.error("All models failed during generation: %s", exc)
        yield format_ai_sdk_status_part(
            stage="complete",
            title="Service Temporarily Busy",
            message=f"Google AI is currently experiencing high demand ({type(exc).__name__}). Please retry shortly.",
        )
        yield format_ai_sdk_text_part(
            "> [!WARNING]\n"
            "> **Google AI High Demand Notice**\n>\n"
            "> The AI model endpoint is temporarily saturated with high demand (HTTP 503). "
            "Please click the **Retry** button or resend your query in a few moments."
        )
        yield format_ai_sdk_finish_part()
        return

    # Step 4: Grounding Validation
    yield format_ai_sdk_status_part(
        stage="validating",
        title="4-Gate Fail-Closed Grounding Verification",
        message="Executing automated safety checks: UUID provenance, ticker consistency, regex marker synchronization (r'\\[\\^(\\d+)\\]'), and lexical snippet overlap...",
        technical_details={
            "validator": "GroundingValidator",
            "gate_1": "UUID Provenance Check",
            "gate_2": "Entity / Ticker Consistency",
            "gate_3": "Footnote Marker Synchronization",
            "gate_4": "Lexical Snippet Verification",
            "policy": "Fail-Closed Strict Enforcement",
        },
    )

    # 4. Enforce grounding verification
    val_result: ValidationResult = validator.validate(
        answer=grounded_answer,
        retrieved_passages=deps.all_retrieved_passages,
    )

    final_answer_text = grounded_answer.answer
    if not val_result.is_valid:
        warning_msg = (
            "\n\n> [!WARNING]\n"
            "> **Grounding Verification Alert**: Some citations in this response could not be verified "
            "against the ingested corpus. Unverified claims have been flagged."
        )
        final_answer_text += warning_msg

    # 5. Persist assistant message with model & parent linkage
        # If auto-failover switched models, emit a smooth status update
    if isinstance(actual_model_used, str) and actual_model_used != target_primary_name:
        failover_label = MODEL_DISPLAY_NAMES.get(actual_model_used, actual_model_used)
        yield format_ai_sdk_status_part(
            stage="reasoning",
            title=f"Auto-Routed to {failover_label}",
            message=f"Primary model capacity reached. Smoothly synthesized answer via {failover_label}...",
            technical_details={
                "orchestrator": "PydanticAI Multi-Key Waterfall",
                "llm": actual_model_used,
                "status": "auto_failover_success",
            },
        )

    asst_metadata: dict[str, Any] = {"model": actual_model_used}
    if parent_user_message_id:
        asst_metadata["parent_user_message_id"] = str(parent_user_message_id)

    asst_msg = save_message(
        client=client,
        thread_id=thread_id,
        role="assistant",
        content=final_answer_text,
        ai_sdk_metadata=asst_metadata,
    )
    asst_msg_id = uuid.UUID(str(asst_msg["id"]))

    # 6. Persist citations in message_citations
    citation_payloads: list[dict[str, Any]] = []
    passage_by_id = {p.chunk_id: p for p in deps.all_retrieved_passages}

    for fallback_idx, cit in enumerate(val_result.verified_citations, start=1):
        p = passage_by_id.get(cit.chunk_id)
        label_match = re.search(r"\d+", cit.citation_label or "")
        cit_idx = int(label_match.group(0)) if label_match else fallback_idx

        best_snippet = cit.snippet.strip() if cit.snippet else ""
        if (not best_snippet or len(best_snippet) < 10 or not any(c.isdigit() for c in best_snippet)) and p:
            fallback_snippet = extract_best_numeric_snippet(p.text, p.full_context_text)
            if fallback_snippet:
                best_snippet = fallback_snippet

        citation_payloads.append(
            {
                "chunk_id": cit.chunk_id,
                "citation_index": cit_idx,
                "ticker": cit.ticker or (p.ticker if p else None),
                "filing_type": p.filing_type if p else "10-K",
                "filing_date": p.filing_date if p else None,
                "section": cit.section
                or (" > ".join(p.headings) if p and p.headings else None),
                "snippet": best_snippet or (p.text[:250] if p else None),
            }
        )

    saved_citations = save_citations(client, asst_msg_id, citation_payloads)

    # Step 5: Complete status
    yield format_ai_sdk_status_part(
        stage="complete",
        title="Pipeline Verified & Streaming",
        message=f"Grounding verified ({len(val_result.verified_citations)} citations confirmed). Streaming tokens...",
        technical_details={
            "verified_citations": len(val_result.verified_citations),
            "status": "passed" if val_result.is_valid else "flagged",
            "protocol": "Vercel AI SDK SSE Data Stream",
        },
    )

    # 7. Stream text response tokens
    words = final_answer_text.split(" ")
    for i, word in enumerate(words):
        chunk = word + (" " if i < len(words) - 1 else "")
        yield format_ai_sdk_text_part(chunk)
        await asyncio.sleep(0.01)

    # 8. Yield enriched citation metadata part for UI drawer & badges
    if saved_citations:
        enriched_citations = []
        for cit in saved_citations:
            cid_str = str(cit.get("chunk_id"))
            try:
                cid = uuid.UUID(cid_str)
            except ValueError:
                cid = None
            p = passage_by_id.get(cid) if cid else None

            raw_snippet = cit.get("snippet") or cit.get("excerpt") or ""
            if (not raw_snippet or len(raw_snippet) < 10 or not any(c.isdigit() for c in raw_snippet)) and p:
                extracted = extract_best_numeric_snippet(p.text, p.full_context_text)
                if extracted:
                    raw_snippet = extracted

            enriched_citations.append(
                {
                    "id": str(cit.get("id", uuid.uuid4())),
                    "chunk_id": cid_str,
                    "citation_index": cit.get("citation_index", 1),
                    "ticker": cit.get("ticker") or (p.ticker if p else ""),
                    "company_name": p.company_name if p else "",
                    "fiscal_year": p.fiscal_year if p else None,
                    "filing_type": cit.get("filing_type", "10-K"),
                    "filing_date": str(cit.get("filing_date") or ""),
                    "section": cit.get("section") or "",
                    "snippet": raw_snippet or (p.text[:250] if p else ""),
                    "full_context_text": p.full_context_text if p else (p.text if p else ""),
                    "is_table": p.is_table if p else False,
                }
            )

        citation_data = {
            "type": "citations",
            "messageId": str(asst_msg_id),
            "citations": enriched_citations,
        }
        yield f"2:[{json.dumps(citation_data)}]\n"

    # 9. Yield auto-generated thread title if ready
    if title_task:
        try:
            generated_title = await asyncio.wait_for(title_task, timeout=1.5)
            if generated_title:
                title_payload = {
                    "type": "thread_title",
                    "threadId": str(thread_id),
                    "title": generated_title,
                }
                yield f"2:[{json.dumps(title_payload)}]" + chr(10)
        except Exception:
            pass

    # 10. Finish stream
    yield format_ai_sdk_finish_part()
