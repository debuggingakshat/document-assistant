# Backend — Document Assistant

FastAPI service for **Document Assistant**, providing grounded SEC 10-K search, citation verification, and real-time streaming for equity research analysts. Python 3.12+ and [uv](https://docs.astral.sh/uv/) required.

---

## Subsystem Architecture & Documentation

The backend is organized into specialized engines with dedicated documentation:

- [Assistant Reasoning Engine (`app/assistant/README.md`)](app/assistant/README.md): PydanticAI agent orchestrator, system prompt contract, tool definitions, and SSE streaming pipeline.
- [Grounding Safety Engine (`app/grounding/README.md`)](app/grounding/README.md): Automated citation validator enforcing fail-closed hallucination rejection and refusal boundaries.
- [Retrieval Engine (`app/retrieval/README.md`)](app/retrieval/README.md): Local dense vector search (BGE-768 on MPS), full-text Postgres search, Reciprocal Rank Fusion (RRF), and context window expansion.

---

## Setup & Running

```bash
cd backend
cp .env.example .env   # fill in real values
uv sync
```

Configuration is managed centrally in `app/config.py`.

### Run Development Server

```bash
uv run uvicorn app.main:app --reload --port 8000
```

- API Base: `http://127.0.0.1:8000`
- Health check: `http://127.0.0.1:8000/health`
- OpenAPI Swagger docs: `http://127.0.0.1:8000/docs`

---

## Database Migrations

Managed via Alembic against Supabase PostgreSQL:

```bash
uv run alembic upgrade head
```

---

## Verification & Testing

```bash
# Run complete test suite (54 tests)
uv run pytest tests/ -v

# Run client-brief 10-question smoke test runner
uv run python scripts/smoke_test_client_brief.py --quick

# Run retrieval verification
uv run python scripts/verify_retrieval.py
```

More setup and migration details: [docs/guides/backend-setup.md](../docs/guides/backend-setup.md).
