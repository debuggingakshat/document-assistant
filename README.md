# Meridian Research Document Assistant

> **Institutional SEC 10-K Equity Research AI Assistant**  
> Audited 10-K Filings for **Apple (`AAPL`)**, **Amazon (`AMZN`)**, **Alphabet (`GOOGL`)**, **Microsoft (`MSFT`)**, and **NVIDIA (`NVDA`)** (FY2021 – FY2025).  
> **Production Deployment ($0.00 / Month)**: [document-assistant-black.vercel.app](https://document-assistant-black.vercel.app)

<p align="left">
  <a href="https://document-assistant-black.vercel.app"><img src="https://img.shields.io/badge/Production-Live%20Demo-000000?style=flat-square&logo=vercel&logoColor=white" alt="Live Demo" /></a>
  <a href="#automated-verification--benchmark-suite"><img src="https://img.shields.io/badge/Tests-71%2F71%20Passing-brightgreen?style=flat-square&logo=pytest&logoColor=white" alt="Automated Tests" /></a>
  <a href="#stage-4-4-gate-fail-closed-grounding-validator"><img src="https://img.shields.io/badge/Grounding-4--Gate%20Fail--Closed-success?style=flat-square&logo=shield&logoColor=white" alt="Grounding Safety" /></a>
  <a href="#license"><img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" alt="License" /></a>
</p>
<p align="left">
  <a href="#core-system-architecture--innovations"><img src="https://img.shields.io/badge/Architecture-Modular%20RAG-orange?style=flat-square" alt="System Architecture" /></a>
  <a href="#stage-1-concurrent-hybrid-retrieval"><img src="https://img.shields.io/badge/Retrieval-Hybrid%20RRF%20(k=60)-blue?style=flat-square" alt="Hybrid RRF Search" /></a>
  <a href="#complete-from-scratch-redevelopment-guide"><img src="https://img.shields.io/badge/Quickstart-Local%20Setup-58a6ff?style=flat-square&logo=git&logoColor=white" alt="Quickstart Runbook" /></a>
  <a href="specifics.md"><img src="https://img.shields.io/badge/Master%20Blueprint-specifics.md%20(25%20Q%26As)-red?style=flat-square" alt="Master Interview Blueprint" /></a>
</p>

---

## Performance & Quality Invariants

| Metric | Measured Value | Engineering Significance |
| :--- | :--- | :--- |
| **Grounding Pass Rate** | **100.0%** (11/11 Verified) | Zero ungrounded claims; 4-Gate Fail-Closed programmatic validation. |
| **Retrieval Top-1 Precision** | **80.0%** (vs. Dense 66.7%) | Reciprocal Rank Fusion ($k=60$) + $\pm 1$ Neighbor Chunk Expansion. |
| **Retrieval Top-5 Recall** | **86.7%** (MRR@5 = 0.822) | Concurrent FTS (`ts_rank_cd`) + Vector Cosine Similarity (`<=>`). |
| **Daily Inference Quota** | **2,160+ Queries / Day** | 2D Waterfall Engine (2 Gemini API Keys $\times$ 6 Cascaded Models at $0.00). |
| **Perceived New Thread Latency** | **0ms (Instantaneous)** | Enterprise Draft Architecture (lazy thread creation on initial prompt). |
| **Corpus Scale** | **2,793 Chunks (25 Filings)** | 8.58 MB pgvector RAM footprint; normalized GitHub-Flavored Markdown tables. |
| **Automated Test Coverage** | **71 / 71 Passing** | Complete test suite across API, auth, chat, grounding, retrieval, follow-ups, and ingest. |

---

## Master Architectural Documentation Map

Every architectural component, compliance rule, and data pipeline is documented across dedicated Markdown specifications. Use this index to navigate the entire system:

| Reference Document | Section / Focus | Key Concepts Covered |
| :--- | :--- | :--- |
| **[`specifics.md`](specifics.md)** | **Master Architectural Blueprint & Staff Interview Guide** | 15 comprehensive technical sections: ETL table normalization, RRF mathematics, 3-layer context window geometry, 4-gate grounding proofs, latency benchmarks, zero-cost topology, and 15 Senior Staff interview mastery Q&As. |
| **[`backend/app/assistant/instructions.md`](backend/app/assistant/instructions.md)** | **Core Agent Compliance & Prompt Directives** | 5-Tier Scope Guardrails (Categories A–E), mandatory in-line citation contracts, dynamic thread onboarding, and anti-repetition conversational dynamics. |
| **[`backend/app/assistant/README.md`](backend/app/assistant/README.md)** | **PydanticAI Reasoning Engine** | Structured output schemas (`GroundedAnswer`), runtime tool execution (`search_filings`, `read_chunk`), and the 2D waterfall failover cascade. |
| **[`backend/app/retrieval/README.md`](backend/app/retrieval/README.md)** | **Hybrid Retrieval Engine** | Dense vector search (`gemini-embedding-001` 768-d), Sparse full-text search (`ts_rank_cd`), RRF ($k=60$), query expansion, and neighbor chunk fusion. |
| **[`backend/app/grounding/README.md`](backend/app/grounding/README.md)** | **4-Gate Grounding Safety Engine** | Gate 1 (UUID Provenance), Gate 2 (Ticker Integrity), Gate 3 (Footnote Sync), and Gate 4 (Verbatim Substring Matching). |
| **[`backend/README.md`](backend/README.md)** | **FastAPI Backend Service** | Async ASGI streaming protocol, SSE data-stream event format, Alembic database migrations, and Supabase service-role authentication. |
| **[`frontend/README.md`](frontend/README.md)** | **React 19 + TypeScript Client** | Zero-latency draft pattern, 4px subtle table micro-scrollbar, real-time pipeline status stepper, rotating starter library, and citation inspection sheets. |
| **[`data/README.md`](data/README.md)** | **SEC EDGAR Ingestion Pipeline** | SEC EDGAR automated retrieval, HTML table normalization, Docling conversion, and 2,793 vector chunk generation. |
| **[`docs/architecture.md`](docs/architecture.md)** | **System Architectural Specification** | Topological request-response flow diagrams, database schemas, and streaming contracts. |
| **[`docs/client-brief.md`](docs/client-brief.md)** | **Meridian Research Client Brief** | Target user personas (buy-side/sell-side equity analysts), operational requirements, and the 10 representative smoke-test questions. |
| **[`docs/guides/supabase-setup.md`](docs/guides/supabase-setup.md)** | **Supabase & Postgres Setup** | Hosted Postgres configuration, `pgvector` & `pg_trgm` extensions, HNSW indexing, and Row-Level Security (RLS) policies. |
| **[`docs/guides/backend-setup.md`](docs/guides/backend-setup.md)** | **Backend Environment Setup** | Step-by-step FastAPI virtualenv creation, dependency sync, and Alembic migrations. |
| **[`docs/guides/frontend-setup.md`](docs/guides/frontend-setup.md)** | **Frontend Environment Setup** | Vite + React scaffold, Tailwind CSS v4 setup, and shadcn/ui components. |
| **[`docs/todos.md`](docs/todos.md)** | **Engineering Implementation Checklist** | Completed milestones across all 9 implementation phases. |

---

## Complete From-Scratch Redevelopment Guide

If you completely delete your local repository or set up a brand-new computer, follow this exact step-by-step runbook to restore, run, and verify the entire platform locally from scratch.

### 1. Prerequisites to Install on Your PC

Ensure the following tools are installed on your machine:

1. **Git**:
   ```bash
   git --version  # Tested on git >= 2.39
   ```
2. **Python 3.12 or 3.13**:
   ```bash
   python3 --version
   ```
3. **[`uv`](https://docs.astral.sh/uv/) (Ultra-Fast Python Package Manager)**:
   ```bash
   # macOS / Linux:
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # Or via Homebrew:
   brew install uv
   ```
4. **Node.js 20+ (LTS) & npm**:
   ```bash
   node --version  # Should be v20.x or v22.x
   npm --version
   ```

---

### 2. External Cloud Accounts & Free Credentials Needed

Before booting the services, gather these free-tier credentials:

1. **Supabase (Database & Authentication)**:
   - Create a free project at [supabase.com](https://supabase.com).
   - In **Project Settings $	o$ API**, copy:
     - `Project URL` (`SUPABASE_URL`)
     - `anon public` key (`SUPABASE_ANON_KEY`)
     - `service_role secret` key (`SUPABASE_SERVICE_ROLE_KEY`)
   - In **Project Settings $	o$ Database $	o$ Connection string**, copy the URI (`DATABASE_URL`).
   - In **Database $	o$ Extensions**, ensure `vector` and `pg_trgm` are enabled.
2. **Google AI Studio (LLM & Embeddings)**:
   - Create an API key at [aistudio.google.com](https://aistudio.google.com/) (100% free).
   - *(Recommended for High-Availability)*: Create a second key under an alternate Google account to unlock the 2D waterfall key rotation (`GEMINI_API_KEY="key1,key2"`).

---

### 3. Step 1: Clone the Repository

```bash
git clone https://github.com/debuggingakshat/document-assistant.git
cd document-assistant
```

---

### 4. Step 2: Backend Environment & Database Setup

Open your terminal in the repository root:

```bash
cd backend

# 1. Create an isolated virtual environment and activate it
uv venv .venv
source .venv/bin/activate

# 2. Install all core and development dependencies
uv pip install -e ".[dev]"

# 3. Configure backend environment variables
cp .env.example .env
```

Edit `backend/.env` with your credentials:

```dotenv
# Supabase Configuration
SUPABASE_URL="https://<your-project-ref>.supabase.co"
SUPABASE_ANON_KEY="<your-supabase-anon-key>"
SUPABASE_SERVICE_ROLE_KEY="<your-supabase-service-role-key>"

# Direct Postgres Connection URI (used by Alembic and SQLAlchemy)
DATABASE_URL="postgresql://postgres:<your-db-password>@db.<your-project-ref>.supabase.co:5432/postgres"

# Google AI Studio Gemini API Keys (comma-separated for dual-key failover)
GEMINI_API_KEY="AIzaSyYourFirstKey,AIzaSyYourSecondKey"
LLM_PROVIDER="gemini"
LLM_MODEL="gemini-3-flash-preview"

# Embeddings (Google AI Studio 768-dim model: 100% free, <90MB RAM footprint)
EMBEDDING_PROVIDER="google"
EMBEDDING_MODEL="gemini-embedding-001"
EMBEDDING_DIMENSIONS=768

# CORS Allowed Origins
ALLOWED_ORIGINS="http://localhost:5173,https://document-assistant-black.vercel.app"
```

#### Apply Database Migrations:
```bash
alembic upgrade head
```
This executes the migration chain in `backend/alembic/versions/` (`0c80fe9acb32_initial_schema.py` and `a2a304490b43_update_embedding_to_768_dim.py`), provisioning `source_documents`, `document_chunks`, `threads`, `messages`, and `message_citations` with vector `<=>` cosine distance and `tsvector` FTS indices.

#### Corpus Verification & Ingestion (2,793 Chunks across 25 Filings):
The pre-processed SEC 10-K filings for Apple, Amazon, Alphabet, Microsoft, and NVIDIA (FY2021–FY2025) are already stored as normalized GFM Markdown in `data/markdown/`.
- If your database is fresh, populate the catalog and run ingestion:
  ```bash
  python ingest/load_source_documents.py
  python ingest/pipeline.py
  ```
- Verify the corpus scale in your Supabase SQL Editor:
  ```sql
  SELECT count(*) FROM source_documents; -- Returns exactly 25
  SELECT count(*) FROM document_chunks;  -- Returns exactly 2,793
  ```

#### Start the FastAPI Server:
```bash
uvicorn app.main:app --reload --port 8000
```
- API Health Check: `http://localhost:8000/health`
- Interactive Swagger UI: `http://localhost:8000/docs`

---

### 5. Step 3: Frontend Environment Setup

Open a second terminal window:

```bash
cd frontend

# 1. Install frontend npm dependencies
npm install

# 2. Configure environment variables
cat << EOF > .env
VITE_API_BASE_URL="http://localhost:8000"
VITE_SUPABASE_URL="https://<your-project-ref>.supabase.co"
VITE_SUPABASE_ANON_KEY="<your-supabase-anon-key>"
EOF

# 3. Start the Vite development server
npm run dev
```

Open your browser to `http://localhost:5173`:
- Create an analyst account using your email (Supabase Auth).
- Click **"New Research Thread"** (initiates instantly with 0ms perceived latency).
- Select any of the 5 live Google models from the input selector (`Gemini 3 Flash`, `Gemini 2.5 Flash`, etc.).
- Start typing financial queries or click any starter suggestion card.

---

## Automated Verification & Benchmark Suite

Document Assistant features a fully automated verification pipeline to mathematically guarantee zero regressions and verify 100% grounded accuracy:

### 1. Complete Pytest Suite (71/71 Passing)
Executes all unit, integration, grounding, follow-ups, and retrieval tests:
```bash
cd backend
.venv/bin/pytest tests -v
```
*Expected Output: `71 passed in ~8s`.*

### 2. Empirical Grounding & Retrieval Benchmark (100% Pass Rate)
Runs the empirical benchmark across live database queries and 4-gate verification:
```bash
cd backend
.venv/bin/python scripts/run_eval_benchmark.py
```
*Empirical Resume Benchmark Results:*
- **Production Top-1 Recall**: **80.0%** (vs. Dense 66.7%, Gain: +13.3%)
- **Production Top-5 Recall**: **86.7%** (vs. Dense 86.7%)
- **Production MRR@5**: **0.822**
- **4-Gate Grounding Pass Rate**: **100.0%** (11/11 verified, 0% ungrounded citations permitted)

### 3. Client Brief 10-Question Smoke Test
Validates the system against all 10 analyst questions from the Meridian Research specification:
```bash
cd backend
.venv/bin/python scripts/smoke_test_client_brief.py --quick
```

### 4. Frontend Production Build Check
Validates TypeScript type safety and minified production asset bundling:
```bash
cd frontend
npm run build
```
*Expected Output: `built in ~300ms` with zero errors.*

---

<a id="stage-1-concurrent-hybrid-retrieval"></a>
<a id="stage-3-pydanticai-reasoning-core--2d-waterfall-engine"></a>
<a id="stage-4-4-gate-fail-closed-grounding-validator"></a>
## Core System Architecture & Innovations

```
                                  [ Analyst Prompt ]
                                          │
                                          ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ REACT 19 FRONTEND (Vite + Tailwind v4 + Radix)                                         │
│ • 0ms Enterprise Draft Pattern (App.tsx / Sidebar.tsx / useChatStream.ts)              │
│ • Dynamic 5-Model Selector (Gemini 3 Flash, 2.5 Flash, 2.0 Flash, 2.0/3.1 Lite)       │
│ • Telemetry Status Stepper (Hybrid Search → RRF Fusion → Reasoning → Validation)       │
│ • Subtle 4px Micro-Scrollbar for GFM Financial Tables (pb-1.5 gutter clearance)       │
└─────────────────────────────────────────┬──────────────────────────────────────────────┘
                                          │ Server-Sent Events (SSE Stream)
                                          ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ FASTAPI ASGI BACKEND (Python 3.13)                                                     │
│ • Sliding Window Memory: Last 6 messages (`LIMIT 6`, assistant turns $\le 350$ chars)  │
│ • Active Ticker Inheritance Engine: Antecedent pronoun resolution (Apple → "their")   │
└─────────────────────────────────────────┬──────────────────────────────────────────────┘
                                          │
                     ┌────────────────────┴────────────────────┐
                     ▼                                         ▼
┌──────────────────────────────────────────┐  ┌──────────────────────────────────────────┐
│ STAGE 1: CONCURRENT HYBRID RETRIEVAL     │  │ STAGE 2: RRF FUSION & EXPANSION          │
│ • Dense: Gemini-Embedding-001 (768-d)    │  │ • Reciprocal Rank Fusion ($k=60$)        │
│ • Sparse: Postgres `ts_rank_cd` FTS      │  │ • $\pm 1$ Neighbor Chunk Graph Expansion │
│ • Target: 2,793 Chunks across 25 Filings │  │ • Produces Top 5 high-density passages   │
└──────────────────────────────────────────┘  └──────────────────────────────────────────┘
                                                               │
                                                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: PYDANTICAI REASONING CORE & 2D WATERFALL ENGINE                               │
│ • System Directives (`instructions.md`): Strict corpus grounding, no causal speculation│
│ • 5-Tier Scope Guardrails: Categories A (Trading Refusal), B (Universe), C (Concepts), │
│   D (Out-of-Domain Refusal), E (Analyst Utility Suite: Spelling, Math, Excel Formulas) │
│ • 2D Waterfall Failover: Model x Key matrix (2 Keys $	imes$ 6 Models = 2,160+ RPD)    │
└─────────────────────────────────────────┬──────────────────────────────────────────────┘
                                          │
                                          ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: 4-GATE FAIL-CLOSED GROUNDING VALIDATOR                                        │
│ • Gate 1: Set-intersection UUID Provenance (strips fabricated chunk IDs)               │
│ • Gate 2: Ticker Entity Alignment (prevents cross-company citation contamination)       │
│ • Gate 3: Footnote Marker Synchronization (syncs `[^1]` markers with citation objects) │
│ • Gate 4: Verbatim Substring Match (validates numerical claims exist in source text)   │
└─────────────────────────────────────────┬──────────────────────────────────────────────┘
                                          │ Verified Factual Payload
                                          ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ STREAMED AUDITABLE RESPONSE TO ANALYST                                                 │
│ • Real-time markdown tokens + in-line citation chips `[^1]`                            │
│ • Interactive Source Drawer: Click citation chip to inspect raw SEC filing text & table│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Production Deployment Topology ($0.00 / Month)

Document Assistant is engineered to operate 100% within free-tier cloud quotas without incurring monthly infrastructure expenses:

| Infrastructure Tier | Provider | Configuration / Spec | Cost / Month |
| :--- | :--- | :--- | :--- |
| **Frontend Web App** | **Vercel** | Edge Network, automatic GitHub CI/CD, React 19 SPA | **$0.00** |
| **Backend API** | **Render** | Free-tier Web Service (Python 3.13, Uvicorn, ASGI) | **$0.00** |
| **Database & Vector Store** | **Supabase** | Free-tier PostgreSQL with `pgvector` & `pg_trgm` | **$0.00** |
| **Foundation LLM & Embeddings** | **Google AI Studio** | Gemini 3 Flash / Flash Lite + Gemini Embedding (2,160+ RPD) | **$0.00** |
| **Total Monthly Operating Cost** | | | **$0.00 / mo** |

---

## Troubleshooting & Engineering Invariants

1. **Python Exception Scoping in Failover Loops**:
   - In Python 3, `except Exception as primary_exc:` deletes the local name variable upon block exit.
   - Preserved `last_exc = primary_exc` *inside* the exception block in `backend/app/chat/orchestrator.py` to prevent `UnboundLocalError` from breaking the waterfall failover cascade.
2. **Database Chunk Count Verification**:
   - Ensure `document_chunks` contains exactly **2,793 chunks** across 25 source filings (not 6,739).
   - If chunk count is off, re-run `python backend/ingest/pipeline.py --force`.
3. **Supabase Connection Pooling**:
   - For Alembic migrations, use port `5432` (Direct connection).
   - For high-concurrency production ASGI workers, use port `6543` (Transaction Pooler).
4. **CORS Headers**:
   - If developing on a custom port, add the origin to `ALLOWED_ORIGINS` in `backend/.env`.

---

## Repository Structure

```
document-assistant/
├── README.md                           # Master Project Overview, Quickstart & Redevelopment Guide
├── specifics.md                        # Complete 15-Section Architectural Blueprint & Interview Guide
├── AGENTS.md                           # Agent Behavior Guidelines & Standards
│
├── backend/                            # FastAPI Backend Service
│   ├── alembic/                        # SQLAlchemy / Alembic Database Migrations
│   │   └── versions/                   # Migration versions (initial schema, 768-dim embeddings)
│   ├── app/
│   │   ├── api/                        # HTTP & SSE Streaming Endpoints (`/chat/stream`, `/threads`)
│   │   ├── assistant/                  # PydanticAI Agent, `instructions.md`, Model Waterfall Cascade
│   │   ├── chat/                       # Orchestrator, Turn Execution, Sliding Window Memory
│   │   ├── grounding/                  # 4-Gate Fail-Closed Grounding Validator
│   │   ├── retrieval/                  # Hybrid Search (Dense + FTS), RRF ($k=60$), Neighbor Expansion
│   │   ├── config.py                   # Pydantic Settings & Multi-Key Extraction
│   │   └── main.py                     # ASGI FastAPI Entrypoint & CORS Middleware
│   ├── ingest/                         # Ingestion Pipeline, Table Cleaner, Chunking & Embedding
│   ├── scripts/                        # Benchmark & Smoke Test Suite (`run_eval_benchmark.py`)
│   ├── tests/                          # 65 Pytest Automated Unit & Integration Tests
│   └── pyproject.toml                  # Backend Dependencies & Package Definitions
│
├── frontend/                           # React 19 + TypeScript Client (Vite + Tailwind v4)
│   ├── src/
│   │   ├── components/chat/            # ChatArea, MessageItem, FinancialTable, Sidebar, Telemetry Stepper
│   │   ├── lib/                        # Chat Streaming Hook (`useChatStream.ts`), Supabase Client
│   │   ├── App.tsx                     # Zero-Latency Route Definition (`/` and `/chat/:threadId`)
│   │   └── index.css                   # Tailwind v4 Theme, 4px Table Micro-Scrollbar Styles
│   └── package.json                    # Frontend Dependencies & Build Scripts
│
├── data/                               # 25 Audited SEC 10-K Filings (FY2021–FY2025)
│   ├── markdown/                       # Cleaned, Normalized GFM Markdown Filings (AAPL, AMZN, GOOGL, MSFT, NVDA)
│   ├── download.py                     # Automated SEC EDGAR Downloader
│   └── README.md                       # Ingestion Data Dictionary & Filing Metadata
│
└── docs/                               # Supporting Architecture Documentation & Setup Guides
    ├── architecture.md                 # System Architecture Blueprint
    ├── client-brief.md                 # Meridian Research Specifications & 10 Test Questions
    ├── todos.md                        # Implementation Roadmap Checklist
    └── guides/                         # Setup Guides (Supabase, Backend, Frontend)
```

---

<a id="license"></a>
## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
