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


COVERED_TICKERS = {"AAPL", "AMZN", "GOOGL", "MSFT", "NVDA"}

UNINDEXED_COMPANIES = {
    "tesla", "tsla", "netflix", "nflx", "meta", "facebook", "uber",
    "disney", "berkshire", "intel", "intc", "amd", "jpmorgan", "jpm",
    "goldman", "goldman sachs", "boeing", "exxon", "walmart", "target",
    "general electric", "ford", "gm", "general motors", "pfizer", "moderna",
}

TRADING_ADVICE_TRIGGERS = [
    r"\bshould\s+i\s+(buy|sell|invest|short|hold|trade)\b",
    r"\b(buy|sell|hold)\s+rating\b",
    r"\bprice\s+target\b",
    r"\bstock\s+recommendation\b",
    r"\bis\s+[a-z0-9]+\s+a\s+(good\s+)?(buy|sell|investment)\b",
    r"\bwhich\s+stock\s+should\s+i\b",
]

ANALYST_UTILITY_TRIGGERS = [
    r"\b=(xirr|xnpv|irr|npv|index|match|sumifs|vlookup)\b",
    r"\b(xirr|xnpv|irr|npv)\s+(formula|in\s+excel|in\s+google\s+sheets)\b",
    r"\b(in|formula\s+in)\s+(excel|spreadsheet|sheets)\b",
    r"\b(cagr|wacc)\s+formula\b",
    r"\b(how\s+do\s+i\s+calculate|formula\s+for|how\s+to\s+calculate)\s+[a-z0-9\s()=]+\s+in\s+excel\b",
    r"\b(is\s+it\s+[a-z]+\s+or\s+[a-z]+|spelling\s+of|how\s+to\s+spell|is\s+it\s+spelled|how\s+is\s+[a-z]+\s+spelled)\b",
    r"\b(renaissance|rennaissance)\b",
    r"\b(convert\s+\d+\s+bps|basis\s+points\s+to\s+percent)\b",
]

FINANCIAL_HISTORY_AND_MACRO_TRIGGERS = [
    # Crises & market panics
    r"\b(2008|subprime)\s+(financial\s+crisis|mortgage\s+crisis|crisis|collapse)\b",
    r"\bfinancial\s+crisis\s+of\s+2008\b",
    r"\b(1987|black\s+monday)\s+(market\s+)?(crash|panic)\b",
    r"\b(1929|great)\s+(market\s+)?(crash|depression)\b",
    r"\bdot[- ]?com\s+(bubble|crash)\b",
    r"\b(tulip\s+mania|south\s+sea\s+bubble|panic\s+of\s+1907)\b",
    r"\b(ltcm|long[- ]term\s+capital\s+management)\b",
    r"\b(lehman\s+brothers|bear\s+stearns)\s+(collapse|bankruptcy|crisis)\b",
    r"\b(subprime\s+mortgage|cdo|cds|credit\s+default\s+swap|mortgage[- ]backed\s+securit)\w*\b",
    r"\b(tarp|troubled\s+asset\s+relief\s+program|bailout|bank\s+bailout)\b",
    # Scandals & forensic accounting
    r"\b(enron|worldcom|tyco|healthsouth|wirecard)\b",
    r"\b(madoff|ponzi\s+scheme)\b",
    r"\b(repo\s+105|accounting\s+scandal|accounting\s+fraud|financial\s+fraud)\b",
    r"\b(special\s+purpose\s+entit\w*|spe\b|mark[- ]to[- ]market\s+accounting)\b",
    # Regulation & central banking
    r"\b(dodd[- ]frank|sarbanes[- ]oxley|sox\b|glass[- ]steagall|volcker\s+rule|basel\s+(i{1,3}|accords?))\b",
    r"\b(federal\s+reserve|monetary\s+policy|quantitative\s+easing|quantitative\s+tightening|interest\s+rate\s+hike)\b",
    r"\b(yield\s+curve\s+inversion|inverted\s+yield\s+curve|liquidity\s+crisis|credit\s+crunch)\b",
    r"\b(capital\s+budgeting|wacc\b|discounted\s+cash\s+flow|dcf\b|capm\b|asc\s+(606|842|350)|goodwill\s+impairment)\b",
]

ELLIPTICAL_FOLLOWUP_INDICATORS = [
    r"\b(they|their|them|that|those|it|its|this)\b",
    r"\b(compare|compared|comparing|comparison|versus|vs\.?)\b",
    r"\b(operating\s+margin|operating\s+income|net\s+income|revenue|sales|capex|cash\s+flow|segment)\b",
    r"\b(202[0-5]|fy2[0-5]|prior\s+year|previous\s+year)\b",
    r"^(and|what\s+about|how\s+about|why\s+did|did\s+they|break\s+down)\b",
]

FILING_METRIC_TERMS = [
    r"\bservices\s+revenue\b",
    r"\bnet\s+sales\b",
    r"\bsegment\s+(operating\s+income|revenue|results)\b",
    r"\boperating\s+income\b",
    r"\bnet\s+income\b",
    r"\bcloud\s+revenue\b",
    r"\bcash\s+payments\s+for\s+property\b",
    r"\bpurchases\s+of\s+property\b",
    r"\bcapital\s+expenditures\b",
    r"\bcapex\b",
    r"\bshare\s+repurchases\b",
    r"\bcash\s+dividends\b",
    r"\bremaining\s+performance\s+obligations\b",
    r"\brpo\b",
    r"\bcustomer\s+concentration\b",
    r"\bresearch\s+and\s+development\s+expense\b",
    r"\br&d\s+expense\b",
    r"\b10[- ]?k\b",
    r"\bannual\s+report\b",
    r"\bsec\s+filing\b",
]

GENERAL_FINANCE_KEYWORDS = [
    "inflation", "deflation", "stagflation", "cpi", "recession",
    "interest rate", "gdp", "central bank", "liquidity", "valuation",
    "equity", "debt", "bond", "treasury", "wacc", "ebitda", "capital budgeting",
    "amortization", "depreciation", "operating margin", "gross margin",
    "financial crisis", "market crash", "ponzi scheme", "forensic accounting",
]


def _extract_all_tickers(query: str) -> set[str]:
    query_upper = query.upper()
    detected = set()
    if "AAPL" in query_upper or "APPLE" in query_upper:
        detected.add("AAPL")
    if "NVDA" in query_upper or "NVIDIA" in query_upper:
        detected.add("NVDA")
    if "MSFT" in query_upper or "MICROSOFT" in query_upper:
        detected.add("MSFT")
    if "AMZN" in query_upper or "AMAZON" in query_upper:
        detected.add("AMZN")
    if (
        "GOOGL" in query_upper
        or "GOOG" in query_upper
        or "ALPHABET" in query_upper
        or "GOOGLE" in query_upper
    ):
        detected.add("GOOGL")
    return detected


def _classify_query_intent(
    user_content: str,
    prior_messages: list[dict[str, Any]],
) -> str:
    """Determine routing path for incoming query across Meridian's 6-Gate Architecture.
    
    Returns one of:
      - 'trading_advice_refusal'
      - 'unindexed_issuer_refusal'
      - 'sec_filing_rag'
      - 'sec_filing_rag_inherited'
      - 'greeting_lifecycle'
      - 'analyst_utility'
      - 'general_finance'
      - 'out_of_domain_refusal'
    """
    lower_query = user_content.lower().strip()
    detected_tickers = _extract_all_tickers(user_content)

    # 1. Trading advice refusal check
    for pat in TRADING_ADVICE_TRIGGERS:
        if re.search(pat, lower_query):
            return "trading_advice_refusal"

    # 2. Unindexed company check (only when no covered tickers are mentioned)
    if not detected_tickers:
        for comp in UNINDEXED_COMPANIES:
            if re.search(rf"\b{comp}\b", lower_query):
                return "unindexed_issuer_refusal"

    # 3. Explicit covered ticker(s) or cross-company comparison (including mixed queries)
    if len(detected_tickers) >= 1:
        return "sec_filing_rag"

    # 4. Analyst utilities & greetings (when no covered ticker explicitly mentioned)
    if _is_low_information_greeting(user_content):
        return "greeting_lifecycle"

    for pat in ANALYST_UTILITY_TRIGGERS:
        if re.search(pat, lower_query):
            return "analyst_utility"

    # 5. Check if it's a general finance, financial history, crisis, or regulatory query
    is_gen_finance = any(re.search(pat, lower_query) for pat in FINANCIAL_HISTORY_AND_MACRO_TRIGGERS)

    # 6. Check elliptical follow-up to prior filing conversation
    # Crucial: NEVER inherit ticker if query is a general finance or unindexed topic!
    if not is_gen_finance and prior_messages:
        has_follow_up_signal = any(re.search(pat, lower_query) for pat in ELLIPTICAL_FOLLOWUP_INDICATORS)
        if has_follow_up_signal:
            for prev in reversed(prior_messages):
                if _extract_all_tickers(prev.get("content", "")):
                    return "sec_filing_rag_inherited"

    if is_gen_finance:
        return "general_finance"

    # 7. Check for filing metric cues without ticker (e.g. "Services revenue?", "10-K filings")
    if any(re.search(pat, lower_query) for pat in FILING_METRIC_TERMS):
        return "sec_filing_rag"

    # 8. Check for general finance terms/questions without filing context
    if any(ft in lower_query for ft in GENERAL_FINANCE_KEYWORDS):
        return "general_finance"

    return "out_of_domain_refusal"



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

    last_exc: Exception | None = None

    # 1. Try provided agent first (handles agent_override in tests)
    try:
        res = await asyncio.wait_for(agent.run(user_content, deps=deps), timeout=75.0)
        return res, target_primary_model
    except Exception as primary_exc:
        last_exc = primary_exc
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
    if last_exc:
        raise last_exc
    raise RuntimeError("All models and keys exhausted in failover waterfall")


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

    # 2. Classify intent and conditionally run Phase 5 hybrid retrieval
    history_records = list_messages(client=client, thread_id=thread_id)
    prior_messages = [
        m for m in history_records
        if m.get("content") and m.get("content").strip() != user_content.strip()
    ][-6:]
    intent = _classify_query_intent(user_content, prior_messages)
    is_filing_query = intent.startswith("sec_filing_rag")

    ticker, fiscal_year = None, None
    retrieval_query = user_content
    if is_filing_query:
        if intent == "sec_filing_rag_inherited":
            _, fiscal_year = _extract_ticker_and_fy(user_content)
            for prev_msg in reversed(prior_messages):
                prev_tickers = _extract_all_tickers(prev_msg.get("content", ""))
                if len(prev_tickers) == 1:
                    ticker = list(prev_tickers)[0]
                    break
            if ticker and ticker not in user_content.upper():
                retrieval_query = f"{user_content} ({ticker})"
        else:
            ticker, fiscal_year = _extract_ticker_and_fy(user_content)

        logger.info(
            "Executing filing retrieval: query='%s', ticker=%s, fy=%s",
            retrieval_query,
            ticker,
            fiscal_year,
        )
        initial_passages = retriever.retrieve(
            query=retrieval_query,
            ticker=ticker,
            fiscal_year=fiscal_year,
            top_n=5,
            expand_neighbors=True,
        )
    else:
        logger.info("Non-filing intent '%s'; bypassing 10-K corpus retrieval", intent)
        initial_passages = []

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


def _is_low_information_greeting(text: str) -> bool:
    """Return True if text is a casual greeting, test, or low-information conversational opener."""
    clean = re.sub(r"[^\w\s]", "", text.strip().lower())
    words = clean.split()
    if not words:
        return True

    # 1. Direct greeting starters (e.g. "hi bud", "hey bro", "hello there", "good morning")
    greeting_starters = {
        "hi", "hello", "hey", "howdy", "greetings", "yo", "sup", "whatsup"
    }
    if len(words) <= 8 and (words[0] in greeting_starters or any(w in greeting_starters for w in words[:2])):
        return True

    # 2. Conversational pleasantries, banter, testing, or departure statements
    casual_words = {
        "hi", "hello", "hey", "howdy", "greetings", "good", "morning", "afternoon", "evening",
        "day", "there", "how", "are", "you", "doing", "yo", "sup", "whatsup", "test", "testing",
        "ok", "okay", "bye", "goodbye", "night", "sleep", "thanks", "thank", "all", "got", "it",
        "understood", "makes", "sense", "no", "that", "thats", "now", "fine", "great", "cool",
        "leave", "bud", "buddy", "bro", "dude", "mate", "friend", "man", "sir", "yes", "yeah", "yep"
    }
    filler_words = {"i", "to", "have", "a", "the", "you", "how", "are", "is", "doing", "it", "me", "my", "we"}
    if len(words) <= 8 and all(w in casual_words or w in filler_words for w in words):
        return True

    return False


async def maybe_generate_thread_title(
    client: Client,
    thread_id: uuid.UUID,
    user_content: str,
    model_name: str | None = None,
) -> str | None:
    """Generate a crisp 3-5 word title for untitled or greeting-titled threads using fast LLM summarization with semantic gating."""
    try:
        thread = get_thread(client, thread_id)
        if not thread:
            return None

        current_title = (thread.get("title") or "").strip()
        is_placeholder_or_greeting = (
            not current_title
            or current_title in ("", "Untitled Analysis", "Untitled Thread", "New Thread")
            or _is_low_information_greeting(current_title)
            or any(
                current_title.lower().startswith(p)
                for p in (
                    "hi", "hello", "hey", "howdy", "yo", "sup", "greetings",
                    "good morning", "good evening", "good afternoon", "ok", "okay", "test"
                )
            )
        )

        if not is_placeholder_or_greeting:
            return None

        # Fast pre-check: If user prompt is an obvious greeting or casual banter, defer titling immediately
        if _is_low_information_greeting(user_content):
            logger.info("Deferred title generation for greeting query: '%s'", user_content)
            return None

        try:
            model = get_llm_model(model_name)
            title_agent: Agent[None, str] = Agent(
                model=model,
                output_type=str,
                system_prompt=(
                    "You are an editor for an SEC equity research system. "
                    "Analyze the user's message to synthesize a concise, professional conversation title.\n\n"
                    "RULES:\n"
                    "1. If the message is a greeting, conversational banter, test, or does NOT ask a substantive question "
                    "(e.g. 'hi bud', 'hey', 'hello there', 'how are you', 'ok leave it i have to sleep', 'test', 'bye', 'thanks'), "
                    "output EXACTLY: UNTITLED\n"
                    "2. If the message asks a substantive financial or research question, synthesize a crisp 3 to 5 word title "
                    "focusing on the company ticker/name and core topic (e.g. 'Amazon FY24 Net Sales', 'Apple Services Gross Margin', 'Nvidia Data Center Growth').\n"
                    "3. Do NOT use quotation marks, punctuation, or generic filler words like 'Analysis of', 'Question about'.\n"
                    "4. Output ONLY the 3-5 word title or UNTITLED."
                ),
            )
            res = await title_agent.run(user_content)
            raw = res.output.strip().strip('"').strip("'").strip()
            clean_title = (raw.splitlines()[0] if raw.splitlines() else raw).strip(".").strip()[:50]

            # LLM Semantic Gate: If the LLM deemed it conversational banter, defer titling
            if not clean_title or clean_title.upper() == "UNTITLED" or clean_title.upper().startswith("UNTITLED"):
                logger.info("LLM semantic gate classified query as non-substantive: '%s'", user_content)
                return None

        except Exception as e:
            logger.warning("LLM title generation failed: %s", e)
            return None

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

    # Classify query intent across Meridian 6-Gate Architecture
    intent = _classify_query_intent(user_content, prior_messages)
    is_filing_query = intent.startswith("sec_filing_rag")

    ticker, fiscal_year = None, None
    inherited_ticker = False
    retrieval_query = user_content

    if is_filing_query:
        if intent == "sec_filing_rag_inherited":
            _, fiscal_year = _extract_ticker_and_fy(user_content)
            for prev_msg in reversed(prior_messages):
                prev_tickers = _extract_all_tickers(prev_msg.get("content", ""))
                if len(prev_tickers) == 1:
                    ticker = list(prev_tickers)[0]
                    inherited_ticker = True
                    logger.info(
                        "Inherited active ticker '%s' from conversation history in thread %s",
                        ticker,
                        thread_id,
                    )
                    break
            if ticker and ticker not in user_content.upper():
                retrieval_query = f"{user_content} ({ticker})"
        else:
            ticker, fiscal_year = _extract_ticker_and_fy(user_content)

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

    active_llm_name = model_name or "gemini-3-flash-preview"
    target_primary_name = MODEL_ALIASES.get(active_llm_name, active_llm_name)
    llm_display_label = MODEL_DISPLAY_NAMES.get(target_primary_name, target_primary_name)

    # 2. Path-aware status emission and context preparation
    if is_filing_query:
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
    else:
        logger.info("Non-filing intent '%s'; proceeding with zero-retrieval context", intent)
        initial_passages = []

        if intent == "general_finance":
            yield format_ai_sdk_status_part(
                stage="reasoning",
                title="Institutional Financial Synthesis",
                message=f"Analyzing macroeconomic principles, financial history, and regulatory frameworks with {llm_display_label}...",
                technical_details={
                    "domain": "Institutional Financial Knowledge",
                    "scope": "Financial History / Macro / Regulatory Policy",
                    "llm": target_primary_name,
                },
            )
        elif intent == "analyst_utility":
            yield format_ai_sdk_status_part(
                stage="reasoning",
                title="Analyst Utility Suite",
                message=f"Evaluating analytical formula / financial utility inquiry with {llm_display_label}...",
                technical_details={
                    "domain": "Analyst Productivity Suite",
                    "utility": "Formulas / Math / Syntax",
                    "llm": target_primary_name,
                },
            )
        elif intent == "greeting_lifecycle":
            yield format_ai_sdk_status_part(
                stage="reasoning",
                title="Meridian Research Session",
                message="Preparing session response...",
                technical_details={
                    "mode": "Conversational Lifecycle",
                    "coverage": "5 Issuers (FY21-FY25)",
                    "llm": target_primary_name,
                },
            )
        else:
            yield format_ai_sdk_status_part(
                stage="reasoning",
                title="Compliance & Scope Verification",
                message="Evaluating inquiry against institutional compliance boundaries...",
                technical_details={
                    "compliance": "Meridian Scope Directives",
                    "intent": intent,
                    "llm": target_primary_name,
                },
            )

    deps = DocumentAgentDeps(
        retriever=retriever,
        initial_passages=initial_passages,
        conversation_history=conversation_history_str,
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

    # If auto-failover switched models, immediately inform the progress stepper
    if isinstance(actual_model_used, str) and actual_model_used != target_primary_name:
        failover_label = MODEL_DISPLAY_NAMES.get(actual_model_used, actual_model_used)
        primary_label = MODEL_DISPLAY_NAMES.get(target_primary_name, target_primary_name)
        yield format_ai_sdk_status_part(
            stage="reasoning",
            title=f"Auto-Routed: {primary_label} → {failover_label}",
            message=f"{primary_label} capacity reached across API keys. Seamlessly switched to {failover_label}...",
            technical_details={
                "orchestrator": "PydanticAI Multi-Key Waterfall",
                "requested_model": primary_label,
                "active_model": failover_label,
                "status": "auto_failover_success",
            },
        )

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
    if is_filing_query:
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
    else:
        yield format_ai_sdk_status_part(
            stage="complete",
            title="Response Verified & Streaming",
            message="Compliance and grounding verified. Streaming response tokens...",
            technical_details={
                "status": "passed" if val_result.is_valid else "flagged",
                "citations": len(val_result.verified_citations),
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
