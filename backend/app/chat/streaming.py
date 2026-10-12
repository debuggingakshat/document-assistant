"""Streaming utilities and stubbed response generation for AI SDK."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from supabase import Client

from app.database.chats import save_message


def format_ai_sdk_text_part(delta: str) -> str:
    """Format a text delta into an AI SDK data stream line."""
    return f"0:{json.dumps(delta)}\n"


def format_ai_sdk_finish_part(finish_reason: str = "stop") -> str:
    """Format a finish part into an AI SDK data stream line."""
    payload = {
        "finishReason": finish_reason,
        "usage": {"promptTokens": 0, "completionTokens": 0},
    }
    return f"d:{json.dumps(payload)}\n"


async def stream_stubbed_chat(
    client: Client,
    thread_id: uuid.UUID,
    user_content: str,
    user_metadata: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    """Persist user message, stream a stubbed assistant reply, and persist the assistant message."""
    # 1. Persist the user message before starting assistant reply
    save_message(
        client=client,
        thread_id=thread_id,
        role="user",
        content=user_content,
        ai_sdk_metadata=user_metadata,
    )

    stubbed_reply = (
        f'I received your question: "{user_content}".\n\n'
        "I am currently running in stubbed mode (Phase 3). "
        "In subsequent phases, I will retrieve relevant passages from SEC 10-K and 10-Q filings, "
        "apply hybrid search with Reciprocal Rank Fusion, and provide grounded answers with citations."
    )

    # 2. Stream tokens in small chunks with realistic delay
    accumulated: list[str] = []
    # Split by spaces while preserving spacing
    words = stubbed_reply.split(" ")
    for i, word in enumerate(words):
        chunk = word + (" " if i < len(words) - 1 else "")
        accumulated.append(chunk)
        yield format_ai_sdk_text_part(chunk)
        await asyncio.sleep(0.02)

    # 3. Yield the completion finish event
    yield format_ai_sdk_finish_part()

    # 4. Persist the complete assistant message to chat_messages
    full_content = "".join(accumulated)
    save_message(
        client=client,
        thread_id=thread_id,
        role="assistant",
        content=full_content,
    )
