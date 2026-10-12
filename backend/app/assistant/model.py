"""LLM model provider initialization for PydanticAI."""

import logging

from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel

from app.config import settings

logger = logging.getLogger(__name__)


def get_llm_model(model_name: str | None = None) -> Model:
    """Return configured PydanticAI model instance.

    Defaults to Google AI Studio Gemini 2.0 Flash (free tier, $0.00 cost).
    """
    target_model = model_name or settings.llm_model or "gemini-3-flash-preview"
    logger.debug("Initializing Google Gemini model: %s", target_model)
    return GoogleModel(target_model)
