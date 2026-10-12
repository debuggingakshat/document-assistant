"""Assistant package for Document Assistant."""

from app.assistant.agent import DocumentAgentDeps, create_document_agent
from app.assistant.model import get_llm_model
from app.assistant.schemas import CitationItem, GroundedAnswer

__all__ = [
    "CitationItem",
    "DocumentAgentDeps",
    "GroundedAnswer",
    "create_document_agent",
    "get_llm_model",
]
