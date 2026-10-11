from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.config import settings

app = FastAPI(title="Document Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/me")
async def me(user: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> dict[str, str]:
    """Test endpoint — returns the authenticated user's id and email."""
    return {"id": str(user.id), "email": user.email}



if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
