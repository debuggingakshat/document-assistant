"""Database access functions for chat threads and messages."""

import uuid
from datetime import UTC, datetime
from typing import Any

from supabase import Client


def ensure_profile(client: Client, user_id: uuid.UUID, email: str) -> None:
    """Ensure a row exists in profiles for foreign key constraints."""
    client.table("profiles").upsert(
        {
            "id": str(user_id),
            "email": email,
        },
        on_conflict="id",
    ).execute()


def create_thread(
    client: Client, user_id: uuid.UUID, title: str | None = None
) -> dict[str, Any]:
    """Create a new chat thread for the given user."""
    payload: dict[str, Any] = {"user_id": str(user_id)}
    if title is not None:
        payload["title"] = title

    response = client.table("chat_threads").insert(payload).execute()
    data = response.data
    if not data or len(data) == 0:
        msg = "Failed to create chat thread"
        raise RuntimeError(msg)
    return data[0]


def list_threads(
    client: Client,
    user_id: uuid.UUID,
    include_archived: bool = False,
    only_archived: bool = False,
) -> list[dict[str, Any]]:
    """List chat threads belonging to the user.

    By default, excludes archived threads and sorts pinned threads first,
    then by updated_at descending.
    """
    query = client.table("chat_threads").select("*").eq("user_id", str(user_id))
    if only_archived:
        query = query.eq("is_archived", True)
    elif not include_archived:
        query = query.eq("is_archived", False)

    query = query.order("is_pinned", desc=True).order("updated_at", desc=True)
    response = query.execute()
    return response.data if response else None or []


def get_thread(client: Client, thread_id: uuid.UUID) -> dict[str, Any] | None:
    """Fetch a single thread by id, or None if not found."""
    response = (
        client.table("chat_threads")
        .select("*")
        .eq("id", str(thread_id))
        .maybe_single()
        .execute()
    )
    return response.data if response else None


def update_thread(
    client: Client,
    thread_id: uuid.UUID,
    title: str | None = None,
    is_pinned: bool | None = None,
    is_archived: bool | None = None,
) -> dict[str, Any]:
    """Update a thread's title, pin status, or archive status."""
    payload: dict[str, Any] = {"updated_at": datetime.now(UTC).isoformat()}
    if title is not None:
        payload["title"] = title
    if is_pinned is not None:
        payload["is_pinned"] = is_pinned
    if is_archived is not None:
        payload["is_archived"] = is_archived

    response = (
        client.table("chat_threads")
        .update(payload)
        .eq("id", str(thread_id))
        .execute()
    )
    data = response.data
    if not data or len(data) == 0:
        msg = "Failed to update thread"
        raise RuntimeError(msg)
    return data[0]


def delete_thread(client: Client, thread_id: uuid.UUID) -> None:
    """Delete a thread by id. Cascades to its messages and citations."""
    client.table("chat_threads").delete().eq("id", str(thread_id)).execute()


def list_messages(
    client: Client,
    thread_id: uuid.UUID,
    include_citations: bool = True,
) -> list[dict[str, Any]]:
    """List all messages in a thread in chronological order, with relational embedded citations."""
    select_query = "*, message_citations(*)" if include_citations else "*"
    response = (
        client.table("chat_messages")
        .select(select_query)
        .eq("thread_id", str(thread_id))
        .order("created_at", desc=False)
        .execute()
    )
    data = response.data if response else None or []
    if include_citations:
        for m in data:
            raw_cits = m.pop("message_citations", []) or []
            for c in raw_cits:
                if not c.get("snippet") and c.get("excerpt"):
                    c["snippet"] = c["excerpt"]
            raw_cits.sort(key=lambda x: x.get("citation_index", 0))
            m["citations"] = raw_cits
    return data


def save_message(
    client: Client,
    thread_id: uuid.UUID,
    role: str,
    content: str,
    ai_sdk_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert a message and update thread's updated_at timestamp."""
    payload: dict[str, Any] = {
        "thread_id": str(thread_id),
        "role": role,
        "content": content,
    }
    if ai_sdk_metadata is not None:
        payload["ai_sdk_metadata"] = ai_sdk_metadata

    response = client.table("chat_messages").insert(payload).execute()
    data = response.data
    if not data or len(data) == 0:
        msg = "Failed to save message"
        raise RuntimeError(msg)

    # Touch thread updated_at
    client.table("chat_threads").update(
        {"updated_at": datetime.now(UTC).isoformat()}
    ).eq("id", str(thread_id)).execute()

    return data[0]


def save_citations(
    client: Client,
    message_id: uuid.UUID,
    citations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Insert normalized citation rows for an assistant message."""
    if not citations:
        return []

    rows: list[dict[str, Any]] = []
    for idx, c in enumerate(citations, start=1):
        rows.append(
            {
                "message_id": str(message_id),
                "chunk_id": str(c["chunk_id"]),
                "citation_index": c.get("citation_index", idx),
                "ticker": c.get("ticker"),
                "filing_type": c.get("filing_type", "10-K"),
                "filing_date": c.get("filing_date"),
                "section": c.get("section"),
                "page": c.get("page"),
                "excerpt": c.get("snippet") or c.get("excerpt"),
            }
        )

    response = client.table("message_citations").insert(rows).execute()
    return response.data if response else None or []


def list_citations(client: Client, message_id: uuid.UUID) -> list[dict[str, Any]]:
    """List all citations linked to a specific assistant message."""
    response = (
        client.table("message_citations")
        .select("*")
        .eq("message_id", str(message_id))
        .order("citation_index", desc=False)
        .execute()
    )
    return response.data if response else None or []
