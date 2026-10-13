"""Unit tests for chat endpoints: threads CRUD, access control, and streaming."""

import uuid
from datetime import UTC, datetime
from unittest.mock import ANY, patch

from fastapi.testclient import TestClient

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.main import app

client = TestClient(app)

_USER_A_ID = uuid.uuid4()
_USER_A = AuthenticatedUser(id=_USER_A_ID, email="user_a@meridianresearch.com")

_USER_B_ID = uuid.uuid4()
_USER_B = AuthenticatedUser(id=_USER_B_ID, email="user_b@meridianresearch.com")

_NOW = datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Unauthenticated tests → 401
# ---------------------------------------------------------------------------


def test_list_threads_unauthenticated():
    resp = client.get("/threads")
    assert resp.status_code == 401


def test_create_thread_unauthenticated():
    resp = client.post("/threads", json={"title": "Test Thread"})
    assert resp.status_code == 401


def test_list_messages_unauthenticated():
    resp = client.get(f"/threads/{uuid.uuid4()}/messages")
    assert resp.status_code == 401


def test_chat_stream_unauthenticated():
    resp = client.post(
        "/chat/stream",
        json={
            "threadId": str(uuid.uuid4()),
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Thread CRUD
# ---------------------------------------------------------------------------


def test_list_threads():
    thread_id = uuid.uuid4()
    mock_threads = [
        {
            "id": str(thread_id),
            "user_id": str(_USER_A_ID),
            "title": "AAPL 10-K analysis",
            "created_at": _NOW,
            "updated_at": _NOW,
        }
    ]

    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with patch("app.api.chat.chats.list_threads", return_value=mock_threads):
            resp = client.get("/threads")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == str(thread_id)
        assert data[0]["title"] == "AAPL 10-K analysis"
    finally:
        app.dependency_overrides.clear()


def test_create_thread():
    thread_id = uuid.uuid4()
    mock_created = {
        "id": str(thread_id),
        "user_id": str(_USER_A_ID),
        "title": "New Thread",
        "created_at": _NOW,
        "updated_at": _NOW,
    }

    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with (
            patch("app.api.chat.chats.ensure_profile") as mock_ensure,
            patch(
                "app.api.chat.chats.create_thread", return_value=mock_created
            ) as mock_create,
        ):
            resp = client.post("/threads", json={"title": "New Thread"})

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == str(thread_id)
        assert data["title"] == "New Thread"
        mock_ensure.assert_called_once()
        mock_create.assert_called_once()
    finally:
        app.dependency_overrides.clear()


def test_update_thread_success():
    thread_id = uuid.uuid4()
    mock_thread = {
        "id": str(thread_id),
        "user_id": str(_USER_A_ID),
        "title": "Old Title",
    }
    mock_updated = {
        "id": str(thread_id),
        "user_id": str(_USER_A_ID),
        "title": "AAPL FY24 10-K Analysis",
        "created_at": _NOW,
        "updated_at": _NOW,
    }

    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with (
            patch("app.api.chat.chats.get_thread", return_value=mock_thread),
            patch(
                "app.api.chat.chats.update_thread", return_value=mock_updated
            ) as mock_update,
        ):
            resp = client.patch(
                f"/threads/{thread_id}", json={"title": "AAPL FY24 10-K Analysis"}
            )

        assert resp.status_code == 200
        assert resp.json()["title"] == "AAPL FY24 10-K Analysis"
        mock_update.assert_called_once_with(
            client=ANY, thread_id=thread_id, title="AAPL FY24 10-K Analysis"
        )
    finally:
        app.dependency_overrides.clear()


def test_update_thread_forbidden_for_other_user():
    thread_id = uuid.uuid4()
    mock_thread_b = {
        "id": str(thread_id),
        "user_id": str(_USER_B_ID),
        "title": "User B Title",
    }

    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with patch("app.api.chat.chats.get_thread", return_value=mock_thread_b):
            resp = client.patch(f"/threads/{thread_id}", json={"title": "New Title"})

        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_update_thread_not_found():
    thread_id = uuid.uuid4()

    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with patch("app.api.chat.chats.get_thread", return_value=None):
            resp = client.patch(f"/threads/{thread_id}", json={"title": "New Title"})

        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_delete_thread_success():
    thread_id = uuid.uuid4()
    mock_thread = {"id": str(thread_id), "user_id": str(_USER_A_ID)}

    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with (
            patch("app.api.chat.chats.get_thread", return_value=mock_thread),
            patch("app.api.chat.chats.delete_thread") as mock_delete,
        ):
            resp = client.delete(f"/threads/{thread_id}")

        assert resp.status_code == 204
        mock_delete.assert_called_once_with(client=ANY, thread_id=thread_id)
    finally:
        app.dependency_overrides.clear()


def test_delete_thread_forbidden_for_other_user():
    thread_id = uuid.uuid4()
    mock_thread_b = {"id": str(thread_id), "user_id": str(_USER_B_ID)}

    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with patch("app.api.chat.chats.get_thread", return_value=mock_thread_b):
            resp = client.delete(f"/threads/{thread_id}")

        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_delete_thread_not_found():
    thread_id = uuid.uuid4()

    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with patch("app.api.chat.chats.get_thread", return_value=None):
            resp = client.delete(f"/threads/{thread_id}")

        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_delete_thread_unauthenticated():
    resp = client.delete(f"/threads/{uuid.uuid4()}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Access Control: 403 and 404
# ---------------------------------------------------------------------------


def test_list_messages_thread_not_found():
    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with patch("app.api.chat.chats.get_thread", return_value=None):
            resp = client.get(f"/threads/{uuid.uuid4()}/messages")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Thread not found"
    finally:
        app.dependency_overrides.clear()


def test_list_messages_forbidden_for_other_user():
    thread_id = uuid.uuid4()
    mock_thread_owned_by_b = {
        "id": str(thread_id),
        "user_id": str(_USER_B_ID),
        "title": "User B Thread",
        "created_at": _NOW,
        "updated_at": _NOW,
    }

    # User A tries to read User B's thread
    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with patch(
            "app.api.chat.chats.get_thread", return_value=mock_thread_owned_by_b
        ):
            resp = client.get(f"/threads/{thread_id}/messages")

        assert resp.status_code == 403
        assert resp.json()["detail"] == "You do not have access to this thread"
    finally:
        app.dependency_overrides.clear()


def test_list_messages_success_for_owner():
    thread_id = uuid.uuid4()
    mock_thread = {
        "id": str(thread_id),
        "user_id": str(_USER_A_ID),
        "title": "User A Thread",
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    mock_messages = [
        {
            "id": str(uuid.uuid4()),
            "thread_id": str(thread_id),
            "role": "user",
            "content": "What is revenue growth?",
            "created_at": _NOW,
            "ai_sdk_metadata": None,
        }
    ]

    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with (
            patch("app.api.chat.chats.get_thread", return_value=mock_thread),
            patch("app.api.chat.chats.list_messages", return_value=mock_messages),
        ):
            resp = client.get(f"/threads/{thread_id}/messages")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["content"] == "What is revenue growth?"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /chat/stream tests
# ---------------------------------------------------------------------------


def test_chat_stream_thread_not_found():
    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with patch("app.api.chat.chats.get_thread", return_value=None):
            resp = client.post(
                "/chat/stream",
                json={
                    "threadId": str(uuid.uuid4()),
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_chat_stream_forbidden_for_other_user():
    thread_id = uuid.uuid4()
    mock_thread_owned_by_b = {
        "id": str(thread_id),
        "user_id": str(_USER_B_ID),
        "title": "User B Thread",
    }

    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with patch(
            "app.api.chat.chats.get_thread", return_value=mock_thread_owned_by_b
        ):
            resp = client.post(
                "/chat/stream",
                json={
                    "threadId": str(thread_id),
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_chat_stream_no_user_message():
    thread_id = uuid.uuid4()
    mock_thread = {"id": str(thread_id), "user_id": str(_USER_A_ID)}

    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with patch("app.api.chat.chats.get_thread", return_value=mock_thread):
            resp = client.post(
                "/chat/stream",
                json={
                    "threadId": str(thread_id),
                    "messages": [{"role": "assistant", "content": "Prior reply"}],
                },
            )
        assert resp.status_code == 400
        assert "No user message found" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_chat_stream_empty_content():
    thread_id = uuid.uuid4()
    mock_thread = {"id": str(thread_id), "user_id": str(_USER_A_ID)}

    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with patch("app.api.chat.chats.get_thread", return_value=mock_thread):
            resp = client.post(
                "/chat/stream",
                json={
                    "threadId": str(thread_id),
                    "messages": [{"role": "user", "content": "   "}],
                },
            )
        assert resp.status_code == 400
        assert "cannot be empty" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_chat_stream_success_emits_ai_sdk_stream():
    thread_id = uuid.uuid4()
    mock_thread = {"id": str(thread_id), "user_id": str(_USER_A_ID)}

    async def mock_stream(*args, **kwargs):
        yield '0:"I received your question."\n'
        yield 'd:{"finishReason": "stop", "usage": {"promptTokens": 0, "completionTokens": 0}}\n'

    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with (
            patch("app.api.chat.chats.get_thread", return_value=mock_thread),
            patch("app.api.chat.stream_orchestrated_turn", side_effect=mock_stream),
        ):
            resp = client.post(
                "/chat/stream",
                json={
                    "threadId": str(thread_id),
                    "messages": [
                        {"role": "user", "content": "Tell me about operating margin"}
                    ],
                },
            )

        assert resp.status_code == 200
        assert resp.headers["x-vercel-ai-data-stream"] == "v1"
        assert "text/plain" in resp.headers["content-type"]

        body_text = resp.text
        assert '0:"I received your question."' in body_text
        assert 'd:{"finishReason": "stop"' in body_text
    finally:
        app.dependency_overrides.clear()


def test_update_thread_pin_and_archive():
    thread_id = uuid.uuid4()
    mock_thread = {
        "id": str(thread_id),
        "user_id": str(_USER_A_ID),
        "title": "Old Title",
    }
    mock_updated = {
        "id": str(thread_id),
        "user_id": str(_USER_A_ID),
        "title": "Old Title",
        "is_pinned": True,
        "is_archived": True,
        "created_at": _NOW,
        "updated_at": _NOW,
    }

    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with (
            patch("app.api.chat.chats.get_thread", return_value=mock_thread),
            patch(
                "app.api.chat.chats.update_thread", return_value=mock_updated
            ) as mock_update,
        ):
            resp = client.patch(
                f"/threads/{thread_id}", json={"is_pinned": True, "is_archived": True}
            )

        assert resp.status_code == 200
        assert resp.json()["is_pinned"] is True
        assert resp.json()["is_archived"] is True
        mock_update.assert_called_once_with(
            client=ANY, thread_id=thread_id, is_pinned=True, is_archived=True
        )
    finally:
        app.dependency_overrides.clear()


def test_list_threads_archived_filter():
    app.dependency_overrides[get_current_user] = lambda: _USER_A
    try:
        with patch("app.api.chat.chats.list_threads", return_value=[]) as mock_list:
            resp = client.get("/threads?archived=true")
            assert resp.status_code == 200
            mock_list.assert_called_once_with(
                client=ANY, user_id=_USER_A_ID, only_archived=True, include_archived=False
            )
    finally:
        app.dependency_overrides.clear()
