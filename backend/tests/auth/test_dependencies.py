"""Unit tests for app.auth.dependencies.

All tests mock the Supabase client — no live network or DB required.
"""

import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_FAKE_USER_ID = uuid.uuid4()
_FAKE_EMAIL = "analyst@driftwood.com"


def _mock_user_response(user_id: uuid.UUID = _FAKE_USER_ID, email: str = _FAKE_EMAIL):
    """Build a fake Supabase UserResponse."""
    user = MagicMock()
    user.id = str(user_id)
    user.email = email
    response = MagicMock()
    response.user = user
    return response


# ---------------------------------------------------------------------------
# Missing / malformed Authorization header → 401
# ---------------------------------------------------------------------------


def test_missing_authorization_header():
    resp = client.get("/me")
    assert resp.status_code == 401


def test_malformed_authorization_header():
    # auto_error=False means non-Bearer schemes yield None credentials,
    # so our get_current_user raises 401 rather than FastAPI's default 403.
    resp = client.get("/me", headers={"Authorization": "NotBearer token"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Valid token → 200
# ---------------------------------------------------------------------------


def test_valid_token_returns_user():
    mock_response = _mock_user_response()
    with patch("app.auth.dependencies.get_service_role_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.auth.get_user.return_value = mock_response
        mock_factory.return_value = mock_client

        resp = client.get("/me", headers={"Authorization": "Bearer valid.jwt.token"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(_FAKE_USER_ID)
    assert data["email"] == _FAKE_EMAIL


# ---------------------------------------------------------------------------
# Supabase returns None (expired / revoked) → 401
# ---------------------------------------------------------------------------


def test_expired_token_returns_401():
    with patch("app.auth.dependencies.get_service_role_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.auth.get_user.return_value = None
        mock_factory.return_value = mock_client

        resp = client.get("/me", headers={"Authorization": "Bearer expired.token"})

    assert resp.status_code == 401


def test_get_user_returns_response_with_none_user_returns_401():
    with patch("app.auth.dependencies.get_service_role_client") as mock_factory:
        mock_client = MagicMock()
        response = MagicMock()
        response.user = None
        mock_client.auth.get_user.return_value = response
        mock_factory.return_value = mock_client

        resp = client.get("/me", headers={"Authorization": "Bearer bad.token"})

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Supabase raises an exception (network error, etc.) → 401
# ---------------------------------------------------------------------------


def test_supabase_exception_returns_401():
    with patch("app.auth.dependencies.get_service_role_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.auth.get_user.side_effect = Exception("Supabase unreachable")
        mock_factory.return_value = mock_client

        resp = client.get("/me", headers={"Authorization": "Bearer some.token"})

    assert resp.status_code == 401
