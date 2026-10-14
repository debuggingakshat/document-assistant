"""LLM model provider initialization for PydanticAI."""

import logging

from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel

from app.config import settings

logger = logging.getLogger(__name__)

# Map any requested aliases to currently active Google AI Studio models with available free quota
MODEL_ALIASES: dict[str, str] = {
    "gemini-3-flash-preview": "gemini-3-flash-preview",
    "gemini-3-flash": "gemini-3-flash-preview",
    "gemini-flash-lite-latest": "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite": "gemini-3.5-flash-lite",
    "gemini-2.5-flash": "gemini-3-flash-preview",
    "gemini-2.5-pro": "gemini-3.5-flash-lite",
    "gemini-2.0-flash": "gemini-3-flash-preview",
    "gemini-2.0-flash-lite": "gemini-flash-lite-latest",
    "gemini-1.5-flash": "gemini-flash-lite-latest",
    "gemini-1.5-pro": "gemini-3.5-flash-lite",
    "gemini-3.8-flash": "gemini-3-flash-preview",
    "gemini-3.6-flash": "gemini-3-flash-preview",
}

FALLBACK_MODELS: list[str] = [
    "gemini-3-flash-preview",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
]


def get_llm_model(model_name: str | None = None) -> Model:
    """Return configured PydanticAI model instance.

    Defaults to Google AI Studio Gemini Flash Preview / Flash Lite (100% free tier, $0.00 cost).
    """
    raw_model = model_name or settings.llm_model or "gemini-3-flash-preview"
    target_model = MODEL_ALIASES.get(raw_model, "gemini-3-flash-preview")
    logger.info("Initializing Google Gemini model: %s (mapped from %s)", target_model, raw_model)
    return GoogleModel(target_model)
