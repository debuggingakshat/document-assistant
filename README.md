# Document Assistant

An internal AI research copilot for senior equity research analysts at **Meridian Research**. Document Assistant allows analysts to query SEC 10-K filings in natural language and receive strictly grounded, fully cited answers with one-click access to the underlying filing excerpts and financial tables.

---

## The Client & Use Case

**Meridian Research** is an independent institutional equity research firm covering major US equities. Prior to Document Assistant, analysts spent ~20 hours per week opening filings, searching for risk factors and segment disclosures, manually comparing year-over-year figures, and compiling intake tables before writing original analysis.

Document Assistant automates this intake workflow while adhering to strict institutional compliance:
- **100% Grounded in Corpus**: Never invents facts or projects non-causal claims.
- **Verbatim Citations**: Every claim and quantitative figure links directly to the filing, fiscal year, and underlying passage.
- **Direct Passage Verification**: Analysts can click any citation chip (`[^1]`, `[^2]`) to view highlighted numerical figures and full surrounding filing context.
- **Institutional Guardrails**: Refuses speculative stock tips, price targets, or unsubstantiated margin causality claims.

For complete background, refer to [docs/client-brief.md](docs/client-brief.md) and [docs/architecture.md](docs/architecture.md).

---

## Technical Stack

| Layer | Technology | Rationale / Specification |
|---|---|---|
| **Backend** | Python 3.12+ / FastAPI | High-concurrency async ASGI API with streaming AI SDK protocol. |
| **Agent / Orchestrator** | PydanticAI v2.52.0 | Type-safe structured outputs (`GroundedAnswer`) with system prompt directives and tool calling. |
| **LLM Provider** | Google Gemini (Free Tier) | Zero-cost inference via Google AI Studio (`gemini-3-flash-preview` / `gemini-flash-lite-latest`) with automatic failover. |
| **Embeddings** | BAAI/bge-base-en-v1.5 | High-accuracy local dense vectors (768 dimensions) via `fastembed` — $0.00 cost, zero API dependency. |
| **Database** | Supabase Postgres + `pgvector` | Hybrid Reciprocal Rank Fusion (pgvector cosine similarity + full-text `tsvector` keyword search). |
| **Frontend** | Vite + React 19 + TypeScript | Premium institutional interface built with Tailwind CSS, shadcn/ui, and Radix primitives. |
| **Observability** | `structlog` | Structured JSON and console logging tracking HTTP latency, retrieval durations, and turn diagnostics. |
| **Multi-Tenancy** | Supabase Auth (JWT) | Complete analyst isolation; database RLS and route verification guarantee zero cross-analyst thread exposure. |

---

## Quickstart — Running Locally

### 1. Prerequisites

- **Python 3.12+** and [`uv`](https://docs.astral.sh/uv/) package manager:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Node.js 20+ (LTS)** and [`pnpm`](https://pnpm.io/):
  ```bash
  corepack enable && corepack prepare pnpm@latest --activate
  ```
- **Supabase Project** with `pgvector` enabled (see [docs/guides/supabase-setup.md](docs/guides/supabase-setup.md)).
- **Google AI Studio API Key** (Free tier available at [aistudio.google.com](https://aistudio.google.com/)).

---

### 2. Backend Setup

```bash
cd backend

# 1. Install dependencies into isolated virtual environment
uv sync

# 2. Configure environment variables
# Copy or edit backend/.env:
cat << 'ENV' > .env
SUPABASE_URL="https://<your-project>.supabase.co"
SUPABASE_ANON_KEY="<your-supabase-anon-key>"
SUPABASE_SERVICE_ROLE_KEY="<your-supabase-service-role-key>"
DATABASE_URL="postgresql://postgres.<your-project>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres"

GEMINI_API_KEY="<your-google-gemini-api-key>"

EMBEDDING_PROVIDER="local"
EMBEDDING_MODEL="BAAI/bge-base-en-v1.5"
EMBEDDING_DIMENSIONS=768

ALLOWED_ORIGINS="http://localhost:5173"
ENV

# 3. Run database migrations
uv run alembic upgrade head

# 4. Start the FastAPI development server
uv run uvicorn app.main:app --reload --port 8000
```
Backend API will be running at `http://localhost:8000` (API documentation at `http://localhost:8000/docs`).

---

### 3. Frontend Setup

```bash
cd frontend

# 1. Install frontend packages
pnpm install

# 2. Configure environment variables
cat << 'ENV' > .env
VITE_API_BASE_URL="http://localhost:8000"
VITE_SUPABASE_URL="https://<your-project>.supabase.co"
VITE_SUPABASE_ANON_KEY="<your-supabase-anon-key>"
ENV

# 3. Start Vite dev server
pnpm dev
```
Open `http://localhost:5173` in your browser. Analysts can sign up or sign in with their email address.

---

## Ingesting & Updating SEC Filings

The sample corpus covers fiscal 2021–2025 10-K filings for Apple (`AAPL`), Microsoft (`MSFT`), NVIDIA (`NVDA`), Amazon (`AMZN`), and Alphabet (`GOOGL`).

### Step 1: Download Filings from SEC EDGAR
Edit `USER_AGENT` in `data/download.py` to match your institutional identity, then run:
```bash
uv run data/download.py
```
This saves HTML filings and generates `data/downloads/manifest.json`.

### Step 2: Seed Source Documents in Supabase
Populate the `source_documents` catalog:
```bash
uv run python backend/ingest/load_source_documents.py
```

### Step 3: Chunk, Embed, and Populate Vector Store
Run the idempotent ingestion pipeline:
```bash
# Ingest full corpus (6,739 chunks across 25 filings)
uv run python backend/ingest/pipeline.py

# Ingest a single company (e.g. Apple)
uv run python backend/ingest/pipeline.py --ticker AAPL

# Force re-chunk and re-embed existing documents
uv run python backend/ingest/pipeline.py --force
```

---

## Automated Smoke Tests & Quality Gates

### 1. Client Brief 10-Question Smoke Test
Validate the assistant against all 10 representative analyst questions from the Meridian client brief:
```bash
# Run all 10 questions
uv run python backend/scripts/smoke_test_client_brief.py

# Run a specific question (e.g. Question 1 or Question 10)
uv run python backend/scripts/smoke_test_client_brief.py --question 1
uv run python backend/scripts/smoke_test_client_brief.py --question 10

# Quick sanity check (Questions 1, 2, and 10)
uv run python backend/scripts/smoke_test_client_brief.py --quick
```

### 2. Backend Pytest Suite
Run all 49 automated unit and integration tests:
```bash
uv run pytest backend/tests -v
```

### 3. Frontend Production Build Check
Verify TypeScript types and Vite production bundling:
```bash
npm run build --prefix frontend
```

---

## Security & Multi-User Isolation

- **Authentication**: All endpoints require a valid Supabase Auth JWT passed via `Authorization: Bearer <token>`.
- **Row-Level Isolation**: Supabase Postgres RLS policies and FastAPI route checks verify `thread.user_id == current_user.id`. Any unauthorized thread access fails fast with `403 Forbidden`.
- **Auditing**: Request latency, caller ID, and failover diagnostics are logged via `structlog`.

---

## Documentation Index & Quick Reference

| Document | Purpose |
| --- | --- |
| [Client Brief](docs/client-brief.md) | Meridian Research requirements, target users, and 10 representative test questions |
| [Architecture Specification](docs/architecture.md) | System design, database schema, data flow, and SSE streaming protocol |
| [Backend Guide](backend/README.md) | FastAPI service setup, environment variables, database migrations, and testing |
| [Assistant Reasoning Engine](backend/app/assistant/README.md) | PydanticAI agent orchestrator, system prompt contract, tool calling, and streaming |
| [Grounding Safety Engine](backend/app/grounding/README.md) | Grounding safety validator, citation verification, and fail-closed refusal contract |
| [Hybrid Retrieval Engine](backend/app/retrieval/README.md) | Dense BGE vector search, Postgres full-text search, RRF fusion, and window expansion |
| [Frontend Guide](frontend/README.md) | Vite + React client, message stream, citation drawers, and theme toggle |
| [Data Ingestion Pipeline](data/README.md) | SEC EDGAR corpus fetching, HTML table cleaner, Docling conversion, and vector indexing |
| [Supabase Setup Guide](docs/guides/supabase-setup.md) | Hosted Postgres, pgvector extension, Auth configuration, and RLS policies |
| [Backend Setup Guide](docs/guides/backend-setup.md) | Step-by-step FastAPI virtualenv and Alembic commands |
| [Frontend Setup Guide](docs/guides/frontend-setup.md) | Vite + React scaffold and styling setup |
| [Implementation Roadmap](docs/todos.md) | Progress checklist across Phases 1 through 9 |
