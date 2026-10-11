"""FastAPI dependency for Supabase JWT verification.

Usage in a route::

    from app.auth.dependencies import CurrentUser, get_current_user

    @router.get("/me")
    async def me(user: CurrentUser) -> dict:
        return {"id": str(user.id), "email": user.email}
"""

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.database.supabase import get_service_role_client

# Extracts `Bearer <token>` from the Authorization header.
# auto_error=False lets us return a clean 401 rather than FastAPI's default 403.
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    """Minimal user identity derived from a verified Supabase JWT."""

    id: uuid.UUID
    email: str


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),  # noqa: B008
) -> AuthenticatedUser:
    """Verify the Supabase bearer token and return the authenticated user.

    Calls Supabase Auth's ``/user`` endpoint with the raw JWT so Supabase
    handles signature verification, expiry, and revocation.  On any failure
    we raise 401 immediately — no retrieval or LLM work runs first.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    client = get_service_role_client()

    try:
        response = client.auth.get_user(token)
    except Exception:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if response is None or response.user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = response.user
    return AuthenticatedUser(id=uuid.UUID(str(user.id)), email=user.email or "")


# Convenient type alias — use as a route parameter type annotation.
CurrentUser = AuthenticatedUser
