"""System instruction loader for the Document Assistant agent."""

from functools import lru_cache
from pathlib import Path

_INSTRUCTIONS_PATH = Path(__file__).resolve().parent / "instructions.md"


@lru_cache(maxsize=1)
def get_system_instructions() -> str:
    """Read and return the cached system instructions for the LLM agent."""
    if not _INSTRUCTIONS_PATH.exists():
        msg = f"System instructions file not found at {_INSTRUCTIONS_PATH}"
        raise FileNotFoundError(msg)
    return _INSTRUCTIONS_PATH.read_text(encoding="utf-8")
