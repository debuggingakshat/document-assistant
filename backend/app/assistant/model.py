"""LLM model provider initialization for PydanticAI."""

import logging
import os

from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from app.config import settings

logger = logging.getLogger(__name__)

# Map requested UI model names & aliases to verified live Google AI Studio endpoints
# Option A: 1-to-1 Model Fidelity - each user selection routes directly to its exact endpoint
MODEL_ALIASES: dict[str, str] = {
    "gemini-3-flash-preview": "gemini-3-flash-preview",
    "gemini-3-flash": "gemini-3-flash-preview",
    "gemini-3.5-flash-lite": "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest": "gemini-flash-lite-latest",
    # Backward compatibility mappings: map legacy flash aliases to high-quota 1,500 RPD endpoints
    "gemini-2.0-flash": "gemini-3.5-flash-lite",
    "gemini-2.5-flash": "gemini-3.5-flash-lite",
    "gemini-2.0-flash-lite": "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite-preview": "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite": "gemini-3.5-flash-lite",
    "gemini-3.8-flash": "gemini-3.8-flash",
    "gemini-3.7-flash": "gemini-3.7-flash",
    "gemini-3.6-flash": "gemini-3.7-flash",
    "gemini-flash-latest": "gemini-flash-latest",
}

# Dynamic fallback sequence unlocking 2,160+ RPD free capacity across dual keys (high quota first)
FALLBACK_MODELS: list[str] = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3-flash-preview",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
]

# Display labels for UI and streaming telemetry
MODEL_DISPLAY_NAMES: dict[str, str] = {
    "gemini-3-flash-preview": "Gemini 3 Flash",
    "gemini-3-flash": "Gemini 3 Flash",
    "gemini-3.8-flash": "Gemini 3.8 Flash",
    "gemini-3.7-flash": "Gemini 3.7 Flash",
    "gemini-3.6-flash": "Gemini 3.6 Flash",
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    "gemini-2.0-flash": "Gemini 2.0 Flash",
    "gemini-2.0-flash-lite": "Gemini 2.0 Flash Lite",
    "gemini-3.5-flash-lite": "Gemini 3.5 Flash Lite",
    "gemini-3.1-flash-lite-preview": "Gemini 3.1 Flash Lite",
    "gemini-3.1-flash-lite": "Gemini 3.1 Flash Lite",
    "gemini-flash-lite-latest": "Gemini Flash Lite",
    "gemini-flash-latest": "Gemini Flash",
}


def get_llm_model(model_name: str | None = None, api_key: str | None = None) -> Model:
    """Return configured PydanticAI model instance with explicit key or provider.

    Defaults to Google AI Studio Gemini Flash Preview / Flash Lite (100% free tier, $0.00 cost).
    """
    raw_model = model_name or settings.llm_model or "gemini-3-flash-preview"
    target_model = MODEL_ALIASES.get(raw_model, raw_model)
    logger.info("Initializing Google Gemini model: %s (mapped from %s)", target_model, raw_model)
    if api_key:
        return GoogleModel(target_model, provider=GoogleProvider(api_key=api_key))
    return GoogleModel(target_model)
