"""Streaming utilities and response generation for AI SDK."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from supabase import Client

from app.database.chats import save_message


def format_ai_sdk_text_part(delta: str) -> str:
    """Format a text delta into an AI SDK data stream line (prefix 0:)."""
    return f"0:{json.dumps(delta)}\n"


def format_ai_sdk_data_part(data: Any) -> str:
    """Format arbitrary structured data into an AI SDK data stream line (prefix 2:)."""
    return f"2:[{json.dumps(data)}]\n"


def format_ai_sdk_status_part(
    stage: str,
    message: str,
    title: str | None = None,
    technical_details: dict[str, Any] | None = None,
) -> str:
    """Format detailed pipeline progress status event for the frontend live indicator."""
    payload: dict[str, Any] = {
        "type": "status",
        "stage": stage,
        "message": message,
    }
    if title:
        payload["title"] = title
    if technical_details:
        payload["technical_details"] = technical_details

    return format_ai_sdk_data_part(payload)


def format_ai_sdk_finish_part(finish_reason: str = "stop") -> str:
    """Format a finish part into an AI SDK data stream line (prefix d:)."""
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

    accumulated: list[str] = []
    words = stubbed_reply.split(" ")
    for i, word in enumerate(words):
        chunk = word + (" " if i < len(words) - 1 else "")
        accumulated.append(chunk)
        yield format_ai_sdk_text_part(chunk)
        await asyncio.sleep(0.02)

    yield format_ai_sdk_finish_part()

    full_content = "".join(accumulated)
    save_message(
        client=client,
        thread_id=thread_id,
        role="assistant",
        content=full_content,
    )
