from functools import lru_cache

from supabase import Client, ClientOptions, create_client

from app.config import settings


@lru_cache(maxsize=1)
def get_service_role_client() -> Client:
    """Return a cached Supabase client initialized with the service-role key.

    Bypasses Row-Level Security (RLS). Used only for privileged server-side
    operations such as ingestion and background indexing.
    """
    return create_client(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_service_role_key,
    )


def get_user_client(access_token: str) -> Client:
    """Return a Supabase client scoped to an authenticated user's JWT.

    Uses the anonymous public key combined with the user's bearer token so that
    Postgres Row-Level Security policies evaluate ``auth.uid()`` properly.
    """
    options = ClientOptions(
        headers={"Authorization": f"Bearer {access_token}"},
    )
    client = create_client(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_anon_key,
        options=options,
    )
    client.postgrest.auth(access_token)
    return client
