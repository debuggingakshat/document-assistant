"""PydanticAI agent definition for Document Assistant."""

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from app.assistant.instructions import get_system_instructions
from app.assistant.model import get_llm_model
from app.assistant.schemas import GroundedAnswer
from app.retrieval.models import RetrievedPassage
from app.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)


@dataclass
class DocumentAgentDeps:
    """Dependencies injected into the Document Assistant agent per run."""

    retriever: Retriever
    initial_passages: list[RetrievedPassage] = field(default_factory=list)
    all_retrieved_passages: list[RetrievedPassage] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.initial_passages and not self.all_retrieved_passages:
            self.all_retrieved_passages = list(self.initial_passages)

    def register_passages(self, passages: Sequence[RetrievedPassage]) -> None:
        """Register newly retrieved passages into the dependency tracking store."""
        existing_ids = {p.chunk_id for p in self.all_retrieved_passages}
        for p in passages:
            if p.chunk_id not in existing_ids:
                self.all_retrieved_passages.append(p)
                existing_ids.add(p.chunk_id)


def create_document_agent(
    model: Model | None = None,
) -> Agent[DocumentAgentDeps, GroundedAnswer]:
    """Factory creating the Document Assistant PydanticAI agent."""
    active_model = model or get_llm_model()

    agent: Agent[DocumentAgentDeps, GroundedAnswer] = Agent(
        model=active_model,
        deps_type=DocumentAgentDeps,
        output_type=GroundedAnswer,
        system_prompt=get_system_instructions(),
    )

    @agent.system_prompt
    def format_retrieved_context(ctx: RunContext[DocumentAgentDeps]) -> str:
        """Inject initial retrieved passages directly into the prompt context."""
        if not ctx.deps.initial_passages:
            return "No pre-retrieved passages available. Use the `search_filings` tool to search."

        lines = [
            "--- RETRIEVED SOURCE PASSAGES IN CONTEXT ---",
            "Use these source passages to construct your answer. Every passage is numbered and has a Chunk ID.",
        ]
        for i, p in enumerate(ctx.deps.initial_passages, start=1):
            table_badge = " [FINANCIAL TABLE]" if p.is_table else ""
            lines.append(
                f"\n[Passage [^{i}] | Chunk ID: {p.chunk_id} | {p.citation_source}{table_badge}]\n"
                f"{p.full_context_text}"
            )
        lines.append("\n--- END OF PASSAGES ---")
        return "\n".join(lines)

    @agent.tool
    async def search_filings(
        ctx: RunContext[DocumentAgentDeps],
        query: str,
        ticker: str | None = None,
        fiscal_year: int | None = None,
        top_n: int = 5,
    ) -> str:
        """Search SEC 10-K filings for additional passages if context is insufficient.

        Args:
            query: Natural language search terms (e.g. 'Azure revenue growth 2024').
            ticker: Optional ticker symbol (e.g. 'MSFT', 'AAPL').
            fiscal_year: Optional fiscal year (e.g. 2024).
            top_n: Number of passages to retrieve (default 5).
        """
        logger.info(
            "Agent searching filings: query='%s', ticker=%s, fy=%s",
            query,
            ticker,
            fiscal_year,
        )
        passages = ctx.deps.retriever.retrieve(
            query=query,
            ticker=ticker,
            fiscal_year=fiscal_year,
            top_n=top_n,
            expand_neighbors=True,
        )

        ctx.deps.register_passages(passages)

        if not passages:
            return f"No matching passages found for query '{query}' (ticker={ticker}, fy={fiscal_year})."

        results = []
        for i, p in enumerate(passages, start=1):
            results.append(
                f"[Tool Result {i} | Chunk ID: {p.chunk_id} | {p.citation_source}]\n{p.full_context_text}"
            )
        return "\n\n---\n\n".join(results)

    @agent.tool
    async def read_chunk(
        ctx: RunContext[DocumentAgentDeps],
        chunk_id: str,
    ) -> str:
        """Retrieve full text and details for a specific chunk ID."""
        try:
            target_uuid = uuid.UUID(chunk_id)
        except ValueError:
            return f"Invalid chunk ID format: {chunk_id}"

        for p in ctx.deps.all_retrieved_passages:
            if p.chunk_id == target_uuid:
                return f"[{p.citation_source}]\n{p.full_context_text}"

        return f"Chunk ID {chunk_id} not found in retrieved session context."

    return agent
