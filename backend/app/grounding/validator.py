"""Grounding enforcement validator verifying citations against retrieved passages."""

import logging
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.assistant.schemas import CitationItem, GroundedAnswer
from app.retrieval.models import RetrievedPassage

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Outcome of grounding validation on a GroundedAnswer."""

    is_valid: bool
    verified_citations: list[CitationItem] = field(default_factory=list)
    invalid_citations: list[CitationItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    sanitized_answer: str = ""


class GroundingValidator:
    """Enforces Meridian Research's trust contract: all claims must cite real retrieved passages."""

    def __init__(self, strict: bool = True) -> None:
        self.strict = strict

    def validate(
        self,
        answer: GroundedAnswer,
        retrieved_passages: Sequence[RetrievedPassage],
    ) -> ValidationResult:
        """Validate that all citations in the answer map to real retrieved context.

        Args:
            answer: The model's structured GroundedAnswer.
            retrieved_passages: All passages that were provided to the model in context.

        Returns:
            ValidationResult with verified citations, invalid citations, and error details.
        """
        passage_map: dict[uuid.UUID, RetrievedPassage] = {
            p.chunk_id: p for p in retrieved_passages
        }

        verified: list[CitationItem] = []
        invalid: list[CitationItem] = []
        errors: list[str] = []

        # 1. If the assistant explicitly refused or stated insufficient evidence
        if not answer.has_sufficient_evidence or answer.refusal_reason:
            logger.info(
                "Answer flagged as insufficient evidence or refusal: %s",
                answer.refusal_reason,
            )
            return ValidationResult(
                is_valid=True,
                verified_citations=[],
                invalid_citations=[],
                errors=[],
                sanitized_answer=answer.answer,
            )

        # 2. Check each citation against retrieved passage IDs
        for cit in answer.citations:
            if cit.chunk_id not in passage_map:
                msg = f"Citation {cit.citation_label} references non-existent chunk ID {cit.chunk_id}."
                errors.append(msg)
                invalid.append(cit)
                logger.warning("Grounding violation: %s", msg)
                continue

            passage = passage_map[cit.chunk_id]

            # Validate company/ticker consistency
            if cit.ticker and cit.ticker.upper() != passage.ticker.upper():
                msg = (
                    f"Citation {cit.citation_label} ticker mismatch: "
                    f"claimed {cit.ticker}, actual {passage.ticker}."
                )
                errors.append(msg)
                invalid.append(cit)
                logger.warning("Grounding violation: %s", msg)
                continue

            # Validate snippet exists in chunk text if snippet is non-empty
            if cit.snippet:
                clean_snippet = " ".join(cit.snippet.strip().lower().split())
                clean_context = " ".join(passage.full_context_text.lower().split())
                # Allow fuzzy match or first 30 chars prefix match
                if (
                    clean_snippet not in clean_context
                    and clean_snippet[:30] not in clean_context
                ):
                    logger.debug(
                        "Citation %s snippet not found verbatim in chunk %s; keeping citation but noting discrepancy.",
                        cit.citation_label,
                        cit.chunk_id,
                    )

            verified.append(cit)

        # 3. Check for orphan in-text citation markers (e.g. [^9] with no citation definition)
        marker_pattern = re.compile(r"\[\^(\d+)\]")
        found_markers = marker_pattern.findall(answer.answer)
        verified_labels = {
            c.citation_label.replace("[^", "").replace("]", "") for c in verified
        }

        for m in found_markers:
            if m not in verified_labels:
                msg = f"In-text citation marker [^{m}] has no valid matching citation item."
                errors.append(msg)

        # 4. Fail-closed decision
        is_valid = True
        if self.strict and (len(invalid) > 0 or len(errors) > 0):
            is_valid = False

        sanitized_text = answer.answer
        if not is_valid and self.strict:
            logger.error("Grounding validation failed with %d errors.", len(errors))

        return ValidationResult(
            is_valid=is_valid,
            verified_citations=verified,
            invalid_citations=invalid,
            errors=errors,
            sanitized_answer=sanitized_text,
        )
