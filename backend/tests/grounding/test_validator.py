"""Unit tests for GroundingValidator."""

import uuid

from app.assistant.schemas import CitationItem, GroundedAnswer
from app.grounding.validator import GroundingValidator
from app.retrieval.models import RetrievedPassage


def _make_passage(
    chunk_id: uuid.UUID | None = None,
    ticker: str = "AAPL",
    fiscal_year: int = 2024,
    text: str = "iPhone sales reached $201 billion in fiscal 2024.",
) -> RetrievedPassage:
    cid = chunk_id or uuid.uuid4()
    return RetrievedPassage(
        chunk_id=cid,
        document_id=uuid.uuid4(),
        ticker=ticker,
        company_name=f"{ticker} Corp",
        fiscal_year=fiscal_year,
        filing_type="10-K",
        filing_date="2024-11-01",
        chunk_index=1,
        text=text,
        full_context_text=text,
        rrf_score=0.03,
        headings=["Item 7. MD&A"],
        citation_source=f"{ticker} FY{fiscal_year} 10-K [Item 7. MD&A]",
    )


def test_valid_grounded_answer() -> None:
    """Properly grounded citations should validate successfully."""
    p1 = _make_passage(text="iPhone net sales were $201,183 million in 2024.")
    p2 = _make_passage(text="Services net sales reached $96,169 million.")

    answer = GroundedAnswer(
        answer="iPhone generated $201,183 million [^1] and Services generated $96,169 million [^2].",
        citations=[
            CitationItem(
                chunk_id=p1.chunk_id,
                citation_label="[^1]",
                ticker="AAPL",
                fiscal_year=2024,
                snippet="$201,183 million",
            ),
            CitationItem(
                chunk_id=p2.chunk_id,
                citation_label="[^2]",
                ticker="AAPL",
                fiscal_year=2024,
                snippet="$96,169 million",
            ),
        ],
        has_sufficient_evidence=True,
    )

    validator = GroundingValidator(strict=True)
    res = validator.validate(answer, [p1, p2])

    assert res.is_valid is True
    assert len(res.verified_citations) == 2
    assert len(res.invalid_citations) == 0
    assert len(res.errors) == 0


def test_hallucinated_chunk_id() -> None:
    """A citation referencing a non-retrieved chunk ID should fail closed."""
    real_p = _make_passage()
    fake_id = uuid.uuid4()

    answer = GroundedAnswer(
        answer="Apple reported massive secret profits [^1].",
        citations=[
            CitationItem(
                chunk_id=fake_id,
                citation_label="[^1]",
                ticker="AAPL",
                fiscal_year=2024,
            )
        ],
        has_sufficient_evidence=True,
    )

    validator = GroundingValidator(strict=True)
    res = validator.validate(answer, [real_p])

    assert res.is_valid is False
    assert len(res.invalid_citations) == 1
    assert "references non-existent chunk ID" in res.errors[0]


def test_ticker_mismatch() -> None:
    """Claiming a passage is from AAPL when it is actually MSFT should fail."""
    msft_p = _make_passage(ticker="MSFT")

    answer = GroundedAnswer(
        answer="Apple cloud revenue doubled [^1].",
        citations=[
            CitationItem(
                chunk_id=msft_p.chunk_id,
                citation_label="[^1]",
                ticker="AAPL",
                fiscal_year=2024,
            )
        ],
        has_sufficient_evidence=True,
    )

    validator = GroundingValidator(strict=True)
    res = validator.validate(answer, [msft_p])

    assert res.is_valid is False
    assert len(res.invalid_citations) == 1
    assert "ticker mismatch" in res.errors[0]


def test_orphan_citation_marker() -> None:
    """Text mentioning [^3] with no matching citation item should produce an error."""
    p1 = _make_passage()

    answer = GroundedAnswer(
        answer="Confirmed figure [^1] and mysterious figure [^3].",
        citations=[
            CitationItem(
                chunk_id=p1.chunk_id,
                citation_label="[^1]",
                ticker="AAPL",
                fiscal_year=2024,
            )
        ],
        has_sufficient_evidence=True,
    )

    validator = GroundingValidator(strict=True)
    res = validator.validate(answer, [p1])

    assert res.is_valid is False
    assert any("marker [^3]" in err for err in res.errors)


def test_refusal_or_insufficient_evidence() -> None:
    """When the assistant refuses or states insufficient evidence, no citations are required."""
    answer = GroundedAnswer(
        answer="I cannot provide stock recommendations or price targets.",
        citations=[],
        has_sufficient_evidence=False,
        refusal_reason="Out of scope: stock advice",
    )

    validator = GroundingValidator(strict=True)
    res = validator.validate(answer, [])

    assert res.is_valid is True
    assert len(res.errors) == 0


def test_educational_financial_concept_answer() -> None:
    """General corporate finance concept questions with no citations should validate cleanly."""
    answer = GroundedAnswer(
        answer=(
            "**Capital budgeting** is the process corporate management uses to evaluate, plan, "
            "and prioritize long-term capital investments such as property, plant, and equipment (PPE). "
            "In SEC 10-K filings, these appear under Capital Expenditures in the Statement of Cash Flows."
        ),
        citations=[],
        has_sufficient_evidence=True,
        refusal_reason=None,
    )

    validator = GroundingValidator(strict=True)
    res = validator.validate(answer, [])

    assert res.is_valid is True
    assert len(res.verified_citations) == 0
    assert len(res.invalid_citations) == 0
    assert len(res.errors) == 0


def test_educational_concept_with_coverage_bridge_citation() -> None:
    """An educational response that cites a specific 10-K example should verify the citation."""
    p = _make_passage(
        ticker="MSFT",
        fiscal_year=2024,
        text="Cash payments for property and equipment were $44,484 million in fiscal 2024.",
    )

    answer = GroundedAnswer(
        answer=(
            "Capital budgeting decisions appear as Capital Expenditures. For example, in FY2024, "
            "Microsoft reported $44,484 million in additions to property and equipment [^1]."
        ),
        citations=[
            CitationItem(
                chunk_id=p.chunk_id,
                citation_label="[^1]",
                ticker="MSFT",
                fiscal_year=2024,
                snippet="$44,484 million",
            )
        ],
        has_sufficient_evidence=True,
        refusal_reason=None,
    )

    validator = GroundingValidator(strict=True)
    res = validator.validate(answer, [p])

    assert res.is_valid is True
    assert len(res.verified_citations) == 1
    assert len(res.invalid_citations) == 0
    assert len(res.errors) == 0


def test_non_financial_domain_refusal() -> None:
    """Non-financial queries (e.g. history, medicine, psychology) should validate cleanly as out-of-domain refusals."""
    answer = GroundedAnswer(
        answer=(
            "As Meridian Research's Document Assistant, I specialize exclusively in institutional equity research, "
            "SEC 10-K filing analysis, and corporate finance/accounting concepts. I cannot assist with non-financial topics "
            "such as psychology. Please feel free to ask questions regarding corporate finance or SEC 10-K disclosures."
        ),
        citations=[],
        has_sufficient_evidence=False,
        refusal_reason="Out of domain: non-financial topic",
    )

    validator = GroundingValidator(strict=True)
    res = validator.validate(answer, [])

    assert res.is_valid is True
    assert len(res.verified_citations) == 0
    assert len(res.invalid_citations) == 0
    assert len(res.errors) == 0
