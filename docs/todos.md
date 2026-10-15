# Document Assistant — implementation checklist

Work top to bottom. Each phase unlocks the next. Check items off as you go.

## Where to start: backend, frontend, or both?

**Start with foundation, then backend-led vertical slices.**

| Order | Why |
| ----- | --- |
| 1. Supabase + sample data | Everything persists here; you need a project and a corpus to test against. |
| 2. Backend schema + migrations | Auth, chat, retrieval, and citations all depend on the data model. |
| 3. Thin vertical slices | Wire auth, then a stubbed chat stream, then real RAG — each slice touches frontend + backend together. |
| 4. Frontend in parallel (lightly) | Scaffold the SPA early, but don't build citation UI or chat polish until the backend can return real grounded answers. |

The critical path is **data model → ingestion → retrieval → LLM → citations**. The frontend is mostly a streaming chat shell with auth and citation display — it shouldn't get far ahead of working APIs.

---

## Phase 0 — Prerequisites & foundation

- [x] Install toolchain: Python 3.12+, `uv`, Node 20+, `pnpm` (see [README](../README.md))
- [x] Create Supabase project and collect credentials ([supabase-setup](guides/supabase-setup.md))
- [x] Create OpenAI API key (needed from Phase 6 onward)
- [x] Set `USER_AGENT` in `data/download.py` and download sample 10-K corpus:
  ```bash
  uv run data/download.py
  ```
- [x] Confirm `data/downloads/manifest.json` lists AAPL, MSFT, NVDA, AMZN, GOOGL filings (2021–2025)

---

## Phase 1 — Backend scaffold & database

Goal: a running FastAPI service with a migrated Supabase schema.

- [x] Init backend deps and project layout ([backend-setup](guides/backend-setup.md))
- [x] `app/config.py` — settings module, fail fast on missing env vars
- [x] `app/main.py` — FastAPI app, CORS, health check (`GET /health`)
- [x] SQLAlchemy models in `app/database/models/`:
  - [x] `users`
  - [x] `source_documents`
  - [x] `document_chunks` (embedding + generated `tsvector`)
  - [x] `chat_threads`
  - [x] `chat_messages`
  - [x] `message_citations`
- [x] Alembic init + first migration:
  - [x] `create extension if not exists vector`
  - [x] `vector(1536)` embedding column
  - [x] generated `tsvector` column on chunks
  - [x] HNSW index (vector) + GIN index (full-text)
  - [x] RLS policies (users see only their own chats)
- [x] `uv run alembic upgrade head` against Supabase direct connection
- [x] `app/database/supabase.py` — user-scoped and service-role clients
- [x] Verify: `uv run uvicorn app.main:app --reload` → health check returns 200

---

## Phase 2 — Auth (full stack)

Goal: analysts can sign in with email; backend rejects unauthenticated requests.

**Backend**

- [x] `app/auth/dependencies.py` — verify `Authorization: Bearer <supabase_jwt>`, expose `get_current_user`
- [x] Reject missing/expired tokens with `401` before any chat or retrieval work

**Frontend**

- [x] Scaffold Vite + React + TypeScript + Tailwind + shadcn ([frontend-setup](guides/frontend-setup.md))
- [x] `src/lib/env.ts` — validate `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- [x] `src/lib/supabase.ts` — browser Supabase client
- [x] `src/lib/http.ts` + `src/lib/api.ts` — fetch wrapper with automatic bearer token
- [x] Sign-in / sign-up pages (email only, no SSO)
- [x] Protected routes — redirect unauthenticated users to login
- [x] Verify: sign up, sign in, token reaches backend on a test authenticated endpoint

---

## Phase 3 — Chat shell (vertical slice, stubbed)

Goal: end-to-end chat UI streaming from FastAPI, no real retrieval yet.

**Backend**

- [x] Chat thread CRUD: list threads, create thread, load message history
- [x] `POST /chat/stream` — accepts AI SDK message format, streams a stubbed assistant reply
- [x] Persist user + assistant messages to `chat_messages` after stream completes
- [x] `403` when user accesses another user's thread

**Frontend**

- [x] React Router: login, chat list, chat thread routes
- [x] AI SDK chat primitives pointed at `POST /chat/stream` with Supabase bearer token
- [x] Thread sidebar (past conversations)
- [x] Basic message list + input + streaming indicator
- [x] Verify: create thread, send message, see streamed stub response, reload and see history

---

## Phase 4 — Ingestion pipeline

Goal: SEC filings in the corpus are parsed, chunked, embedded, and stored in Supabase.

- [x] `ingest/` scripts (CLI entrypoint `pipeline.py` with batching & idempotency)
- [x] HTML → normalized Markdown extraction (preserve page/section metadata)
- [x] Chunking strategy (Docling HybridChunker + tiktoken 800 token budget + deduplication)
- [x] Write `source_documents` rows with filing metadata from `manifest.json`
- [x] Write `document_chunks` rows with text + metadata (6,739 chunks)
- [x] Local BGE embedding generation → store `vector(768)` per chunk ($0.00 cost)
- [x] Generated `tsvector` populated for full-text search
- [x] Idempotent re-run (skip already-ingested documents)
- [x] Unit tests: chunking logic, metadata extraction
- [x] Run ingestion on full sample corpus (25 filings × 5 companies — 6,739 chunks)
- [x] Verify: chunks exist in Supabase; 6,739 chunks verified across 68 pages

---

## Phase 5 — Retrieval

Goal: a user question returns ranked, relevant source passages.

- [x] `retrieval/queries.py` — pgvector semantic search over `document_chunks`
- [x] `retrieval/queries.py` — Postgres full-text search over `search_vector`
- [x] `retrieval/fusion.py` — Reciprocal Rank Fusion in Python
- [x] `retrieval/retriever.py` — query → fused ranked passages + neighbor chunks
- [x] Unit tests: fusion ranking, query assembly (mock DB)
- [x] Integration test (optional, `@pytest.mark.integration`): real query against ingested corpus
- [x] Verify: test queries from [client-brief](client-brief.md) return relevant chunks (manual or scripted)

---

## Phase 6 — LLM agent & grounding

Goal: grounded answers with enforced citations — the core product contract.

- [x] `assistant/instructions.md` — product contract (cite everything, refuse to invent, no stock picks)
- [x] PydanticAI agent with typed deps (`DocumentAgentDeps`) and output (`GroundedAnswer`)
- [x] Agent tools: `search_filings`, `read_chunk`, `read_surrounding_chunks`
- [x] `chat/orchestrator.py` — one turn: retrieve → agent → validate → stream → persist
- [x] `grounding/validator.py` — every citation maps to a retrieved passage; fail closed on violation
- [x] `chat/streaming.py` — AI SDK-compatible stream (text deltas + citation metadata parts)
- [x] Persist `message_citations` linked to assistant messages
- [x] Unit tests: citation validation, grounding enforcement, message conversion
- [x] Verify against [client-brief example questions](client-brief.md#example-analyst-questions):
  - [x] Answers cite specific filings and pages
  - [x] Under-specified questions get "not enough evidence" responses
  - [x] Question 10 (generative AI margins) refuses to infer beyond filings

---

## Phase 7 — Trust UI (citations & source passages)

Goal: analysts can verify every claim in one click — this is what makes the product usable.

- [x] Citation chips/links on assistant messages (company, filing type, date, page/section)
- [x] Source passage panel — show underlying excerpt for selected citation
- [x] Empty states (no threads, no corpus match)
- [x] Error states (auth expired, retrieval failure, grounding failure, network/CORS)
- [x] Loading/streaming status during assistant run
- [x] Verify: click a citation → see the exact passage from the filing

---

## Phase 8 — Pilot readiness

Goal: 5 senior analysts can use it for a week and report ≥3 hours saved per analyst per week.

- [x] README "Running locally" section — copy-paste commands for backend + frontend + env vars
- [x] Seed or document how to ingest/update the corpus
- [x] Smoke-test all 10 example questions from the client brief
- [x] Confirm chat history persists across sessions
- [x] Confirm ~40-user scale assumptions (no hardcoded single-user shortcuts)
- [x] Basic structured logging on backend (`structlog`) for debugging failed turns
- [x] Review latency: streaming starts within a few seconds for typical queries

---

## Phase 9 — Deployment (Vercel + Render)

Goal: 100% free production deployment with global CDN for frontend (Vercel) and 512 MB Free Web Service for backend (Render), powered by Google AI Studio 768-dim Embeddings (<100 MB RAM).

### Frontend Deployment (Vercel)
- [x] Create `frontend/vercel.json` with SPA route rewrites to prevent 404s on page refresh
- [x] Connect GitHub repository to Vercel with Root Directory set to `frontend`
- [x] Set frontend environment variables (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE_URL`)
- [x] Deploy Vite build to Vercel production CDN (`https://document-assistant-black.vercel.app`)
- [x] Add Meridian Research branding, logo, and theme toggle to auth pages (`/login`, `/signup`)
- [x] Configure Supabase Auth Redirect URLs to allow Vercel domain

### Backend Optimization (Google API 768-dim Embeddings)
- [x] Remove PyTorch (`torch`, `sentence-transformers`) and ONNX from `backend/pyproject.toml`
- [x] Add `google-genai` to dependencies and delete local cached model weights (~450MB SSD reclaimed)
- [x] Implement `GoogleEmbedder` in `backend/ingest/embedder.py` using `gemini-embedding-001` (output_dimensionality=768)
- [x] Update `backend/app/retrieval/retriever.py` to use `GoogleEmbedder`
- [x] Verify memory footprint stays under ~90 MB (measured 89.0 MB, safely below Render 512 MB ceiling)

### Database Reset & Re-Ingestion
- [x] Wipe test data from Supabase (`chat_threads`, `chat_messages`, `message_citations`, `profiles`)
- [x] Wipe old 768-dim BGE vectors from `document_chunks` (keeping `source_documents` intact)
- [x] Re-ingest all 25 filings via `pipeline.py` with Google 768-dim embeddings (2,793 chunks)
- [x] Verify hybrid retrieval and vector consistency (`verify_retrieval.py` - passed on all 5 companies)
- [x] Run automated pytest suite (54/54 tests passed) and client-brief smoke tests

### Backend Deployment (Render)
- [x] Add CORS `ALLOWED_ORIGINS` in backend configuration for `https://document-assistant-black.vercel.app`
- [x] Add root discovery endpoint (`/`) and health check (`/health`)
- [x] Create free Web Service on Render from GitHub repository (`Root Directory: backend`)
- [x] Set Build Command (`pip install uv && uv sync --frozen --no-dev`) and Start Command (`.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $PORT`)
- [x] Add Render environment variables (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`, etc.)
- [x] Deploy and verify backend `/health` and `/docs` on live Render URL (`https://document-assistant-backend-om3b.onrender.com`)

### Multi-Turn Conversational Memory
- [x] Fetch recent thread dialogue turns (up to 6 messages) from Supabase via `chats.list_messages`
- [x] Implement active ticker/entity inheritance for follow-up questions omitting company names
- [x] Inject `--- PRIOR CONVERSATION HISTORY ---` directly into PydanticAI agent context (`agent.py`)
- [x] Add multi-turn directives to `instructions.md` for narrative continuity and metric consistency
- [x] Add automated unit test `test_multi_turn_ticker_inheritance` (55/55 tests passing)

### Scope Boundaries & Educational Concept Handling
- [x] Refactor Directive 4 in `instructions.md` into 4 distinct categories: Trading Advice Refusal, Coverage Universe Boundary, Finance & Accounting Concepts Only, and Non-Financial Topic Refusal
- [x] Add Category C educational bridge: define corporate finance concepts (e.g., capital budgeting, EBITDA, WACC, ASC 606) and bridge to 10-K sections (MD&A Item 7, Cash Flow Statement CapEx)
- [x] Add Category D domain boundary: strictly refuse non-financial subjects (history, psychology, medical, pop culture) and redirect user to finance and 10-K research
- [x] Update `GroundedAnswer` schema in `schemas.py` to clarify that corporate finance definitions do not trigger refusal flags while non-financial topics set domain refusal
- [x] Add automated unit tests in `test_validator.py` and `test_orchestrator.py` for both finance education and non-financial domain refusals (60/60 tests passing)

### Integration & Verification
- [x] Update Vercel `VITE_API_BASE_URL` with the live Render backend URL (`https://document-assistant-backend-om3b.onrender.com`)
- [x] Deploy frontend to Vercel production CDN (`https://document-assistant-black.vercel.app`)
- [ ] End-to-end test on deployed URLs: analyst login, chat streaming, citation inspection drawer, and financial tables

---

## Quick reference

### Project & Subsystem READMEs

| Doc | Purpose |
| --- | ------- |
| [README.md](../README.md) | Root project overview, architecture, quickstart, client brief compliance |
| [backend/README.md](../backend/README.md) | FastAPI service setup, environment variables, test commands |
| [frontend/README.md](../frontend/README.md) | React + Vite client, citation drawer, theme support |
| [data/README.md](../data/README.md) | SEC EDGAR corpus, HTML-to-Markdown pipeline, SEC table cleaner |
| [backend/app/assistant/README.md](../backend/app/assistant/README.md) | PydanticAI agent, system prompt contract, reasoning architecture |
| [backend/app/grounding/README.md](../backend/app/grounding/README.md) | Grounding safety validator, citation verification, refusal contract |
| [backend/app/retrieval/README.md](../backend/app/retrieval/README.md) | Hybrid dense vector + keyword search, RRF rank fusion, neighbor expansion |

### Architecture & Specification Guides

| Doc | Purpose |
| --- | ------- |
| [client-brief.md](client-brief.md) | What Meridian Research needs and example questions |
| [architecture.md](architecture.md) | System design, data model, streaming contract |
| [guides/supabase-setup.md](guides/supabase-setup.md) | Hosted Postgres + Auth + pgvector setup |
| [guides/backend-setup.md](guides/backend-setup.md) | FastAPI + Alembic commands and environment |
| [guides/frontend-setup.md](guides/frontend-setup.md) | Vite + React scaffold commands and config |