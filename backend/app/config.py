import os
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_url: str = Field(min_length=1)
    supabase_anon_key: str = Field(min_length=1)
    supabase_service_role_key: str = Field(min_length=1)
    database_url: str = Field(min_length=1)

    # LLM configuration (Google Gemini free tier)
    gemini_api_key: str = Field(default="")
    google_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")
    llm_provider: str = Field(default="gemini")
    llm_model: str = Field(default="gemini-3-flash-preview")

    # Embedding configuration: Google AI Studio 768-dim model (100% free, <90MB RAM)
    embedding_provider: str = "google"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768
    openai_embedding_model: str = "gemini-embedding-001"
    openai_embedding_dimensions: int = 768

    allowed_origins: Annotated[list[str], NoDecode] = Field(min_length=1)

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()

# Sync API keys with environment for Google & OpenAI libraries
effective_gemini_key = settings.gemini_api_key or settings.google_api_key
if effective_gemini_key:
    primary_key = effective_gemini_key.split(",")[0].strip()
    os.environ["GOOGLE_API_KEY"] = primary_key
    os.environ["GEMINI_API_KEY"] = primary_key

if settings.openai_api_key:
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key
