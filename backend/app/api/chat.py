"""Chat API router for thread management and AI streaming."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.chat.orchestrator import stream_orchestrated_turn
from app.database import chats
from app.database.supabase import get_service_role_client

router = APIRouter(tags=["chat"])


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------


class CreateThreadRequest(BaseModel):
    title: str | None = None


class UpdateThreadRequest(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    is_pinned: bool | None = None
    is_archived: bool | None = None


class ThreadResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str | None = None
    is_pinned: bool = False
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    ai_sdk_metadata: dict[str, Any] | None = None


class ChatStreamRequest(BaseModel):
    thread_id: uuid.UUID = Field(
        validation_alias=AliasChoices("threadId", "thread_id"),
    )
    messages: list[dict[str, Any]] = Field(default_factory=list)
    model: str | None = None
    parent_user_message_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("parentUserMessageId", "parent_user_message_id"),
    )

    model_config = ConfigDict(populate_by_name=True)


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------


@router.get("/threads", response_model=list[ThreadResponse])
async def list_threads(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    archived: bool = False,
) -> list[dict[str, Any]]:
    """List all chat threads belonging to the authenticated user."""
    client = get_service_role_client()
    return chats.list_threads(
        client=client,
        user_id=user.id,
        only_archived=archived,
        include_archived=False,
    )


@router.post(
    "/threads", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED
)
def create_thread(
    body: CreateThreadRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """Create a new chat thread for the authenticated user."""
    client = get_service_role_client()
    chats.ensure_profile(client=client, user_id=user.id, email=user.email)
    return chats.create_thread(client=client, user_id=user.id, title=body.title)


@router.patch("/threads/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: uuid.UUID,
    body: UpdateThreadRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """Update a chat thread (rename, pin, archive)."""
    client = get_service_role_client()
    thread = chats.get_thread(client=client, thread_id=thread_id)
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    if str(thread.get("user_id")) != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this thread",
        )

    kwargs: dict[str, Any] = {}
    if body.title is not None:
        kwargs["title"] = body.title.strip()
    if body.is_pinned is not None:
        kwargs["is_pinned"] = body.is_pinned
    if body.is_archived is not None:
        kwargs["is_archived"] = body.is_archived

    return chats.update_thread(
        client=client,
        thread_id=thread_id,
        **kwargs,
    )


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> None:
    """Delete a chat thread and all its messages."""
    client = get_service_role_client()
    thread = chats.get_thread(client=client, thread_id=thread_id)
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    if str(thread.get("user_id")) != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this thread",
        )

    chats.delete_thread(client=client, thread_id=thread_id)


@router.get("/threads/{thread_id}/messages", response_model=list[MessageResponse])
async def list_thread_messages(
    thread_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    """Load message history for a specific thread."""
    client = get_service_role_client()
    thread = chats.get_thread(client=client, thread_id=thread_id)
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    if str(thread.get("user_id")) != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this thread",
        )

    return chats.list_messages(client=client, thread_id=thread_id)


@router.get("/messages/{message_id}/citations")
async def list_message_citations(
    message_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    """Fetch stored citations for a specific assistant message."""
    client = get_service_role_client()
    return chats.list_citations(client=client, message_id=message_id)


@router.post("/chat/stream")
async def chat_stream(
    body: ChatStreamRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> StreamingResponse:
    """Stream an assistant reply in AI SDK-compatible format."""
    client = get_service_role_client()

    # 1. Verify thread existence and ownership
    thread = chats.get_thread(client=client, thread_id=body.thread_id)
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    if str(thread.get("user_id")) != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this thread",
        )

    # 2. Extract latest user message
    user_message: dict[str, Any] | None = None
    for msg in reversed(body.messages):
        if msg.get("role") == "user":
            user_message = msg
            break

    if user_message is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No user message found in conversation payload",
        )

    raw_content = user_message.get("content")
    content = ""
    if isinstance(raw_content, str):
        content = raw_content.strip()

    if not content:
        parts = user_message.get("parts")
        if isinstance(parts, list):
            text_parts = [
                p.get("text", "")
                for p in parts
                if isinstance(p, dict) and p.get("type") == "text"
            ]
            content = " ".join(text_parts).strip()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User message content cannot be empty",
        )

    parsed_parent_id: uuid.UUID | None = None
    if body.parent_user_message_id:
        try:
            parsed_parent_id = uuid.UUID(str(body.parent_user_message_id))
        except (ValueError, TypeError):
            db_user_msgs = [
                m for m in chats.list_messages(client, body.thread_id)
                if m.get("role") == "user"
            ]
            if db_user_msgs:
                parsed_parent_id = uuid.UUID(str(db_user_msgs[-1]["id"]))

    return StreamingResponse(
        stream_orchestrated_turn(
            client=client,
            thread_id=body.thread_id,
            user_content=content,
            user_metadata=user_message,
            model_name=body.model,
            parent_user_message_id=parsed_parent_id,
        ),
        media_type="text/plain; charset=utf-8",
        headers={"x-vercel-ai-data-stream": "v1"},
    )
