"""Structured schemas for grounded assistant answers and citations."""

import uuid

from pydantic import BaseModel, Field


class CitationItem(BaseModel):
    """A citation mapping an in-line claim to a specific filing chunk."""

    chunk_id: uuid.UUID
    citation_label: str = Field(
        description="In-line citation label such as [^1] or [^2]"
    )
    ticker: str = Field(description="Company stock ticker, e.g. AAPL")
    company_name: str = Field(default="", description="Full company name")
    fiscal_year: int = Field(description="Filing fiscal year, e.g. 2024")
    filing_type: str = Field(default="10-K", description="Filing type, e.g. 10-K")
    section: str = Field(
        default="", description="Section or item heading, e.g. Item 7. MD&A"
    )
    snippet: str = Field(
        default="", description="Exact quote or phrase supporting the claim"
    )


class GroundedAnswer(BaseModel):
    """The structured, grounded response produced by the Document Assistant."""

    answer: str = Field(
        description="Markdown formatted analyst answer with in-line citation indicators like [^1], [^2]."
    )
    citations: list[CitationItem] = Field(
        default_factory=list,
        description="List of all citations cited in the answer, referencing retrieved chunks.",
    )
    has_sufficient_evidence: bool = Field(
        default=True,
        description="Whether the retrieved corpus had sufficient evidence to answer.",
    )
    refusal_reason: str | None = Field(
        default=None,
        description="Set if the request was refused due to scope (e.g. stock trading advice, non-coverage entity, or non-financial domain topic). Leave None for corporate finance definitions.",
    )
