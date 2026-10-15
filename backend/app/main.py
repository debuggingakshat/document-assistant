import time
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.config import settings
from app.logging import get_logger, setup_logging

setup_logging()
logger = get_logger("app.main")

app = FastAPI(title="Document Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log incoming HTTP requests with latency tracking for observability."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    if request.url.path not in ("/health",):
        logger.info(
            "http_request_completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
    return response


app.include_router(chat_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "Document Assistant Backend API",
        "status": "online",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/me")
async def me(user: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> dict[str, str]:
    """Test endpoint — returns the authenticated user's id and email."""
    return {"id": str(user.id), "email": user.email}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
