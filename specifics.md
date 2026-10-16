# Document Assistant: Technical Specification & Architecture

## 1. System Overview & Architecture Topology

Document Assistant is an institutional financial research engine built for equity analysts at **Meridian Research**. It conducts SEC 10-K filing analysis across 5 mega-cap technology issuers (**AAPL, AMZN, GOOGL, MSFT, NVDA**) spanning **FY2021 through FY2025** (25 annual reports).

The platform guarantees **absolute factual provenance**: every numeric claim, margin figure, and trend observation is linked to a verifiable filing chunk via a **4-Gate Fail-Closed Grounding Validator**. The entire stack operates on a **100% free tier ($0.00 / ₹0)** footprint across production cloud services.

```
[ Frontend: React 19 + Vite ] (Vercel Edge CDN)
       │ HTTP POST /api/chat (SSE Stream)
       ▼
[ Backend: FastAPI + PydanticAI ] (Render Free Web Service)
       ├── Ingestion: SEC HTML -> Markdown Cleaner -> Semantic Chunker
       ├── Storage: Supabase PostgreSQL 15 + pgvector (768-dim HNSW)
       ├── Embeddings: Google gemini-embedding-001 (Multi-Key Rotation Pool)
       ├── Retrieval: Hybrid RRF Fusion (Vector <=> + Full-Text Search tsquery)
       ├── Reasoning: Google Gemini 3 Flash / 2.5 Flash Failover
       └── Guardrails: 4-Gate Fail-Closed Grounding Validator
```

---

## 2. Ingestion & Document Processing Pipeline

The ingestion pipeline converts multi-megabyte SEC EDGAR HTML filings into structured, semantically searchable markdown chunks.

1. **Extraction & Sanitization (`cleaner.py` / `sec_table_cleaner.py`)**:
   - Parses EDGAR raw HTML, stripping boilerplate headers, navigation tags, and uninformative XML.
   - Converts financial HTML tables into clean GitHub Flavored Markdown (GFM) grids.
   - Normalizes numeric rows (retaining parentheses for negative values, currency symbols, and units in millions/billions).
   - Detects nested tables and consolidates multi-row headers into unified column identifiers.

2. **Semantic Chunking (`chunker.py`)**:
   - Splits documents hierarchically on SEC Item boundaries (`Item 1. Business`, `Item 7. MD&A`, `Item 8. Financial Statements`).
   - Token-bounded chunking: Target size **600–900 tokens** with **150-token overlapping sliding windows**.
   - Preserves complete financial tables: tables exceeding token thresholds are split across rows while repeating header rows for semantic coherence.
   - **Bidirectional Linked Chunks**: Each chunk stores `prev_chunk_id` and `next_chunk_id` foreign keys, enabling runtime context expansion without re-querying the database.

3. **Multi-Key Embedding Generation (`embedder.py`)**:
   - Vectorized using Google AI Studio's **`gemini-embedding-001`** (768 dimensions).
   - Implements a **Multi-Key Round-Robin & Failover Pool**: when Google triggers an HTTP 429 quota exhaustion, the pipeline rotates to the next active key with exponential backoff.
   - Total ingested corpus: **25 filings = 2,793 chunks** stored in Supabase `document_chunks`.

---

## 3. Hybrid Retrieval & Rank Fusion (RAG)

Standard vector search struggles with exact financial numbers, while pure keyword search misses conceptual synonyms. Document Assistant solves this with **Hybrid Reciprocal Rank Fusion (RRF)**.

1. **Dense Vector Search**:
   - Computes cosine distance (`<=>` operator in pgvector) between the 768-dim query embedding and chunk vectors:
     $$\text{Cosine Similarity} = 1 - (\vec{u} \cdot \vec{v})$$
   - Uses HNSW indexes (`m=16`, `ef_construction=64`) for sub-10ms nearest-neighbor scans.

2. **Sparse Full-Text Search**:
   - Queries a PostgreSQL `tsvector` column (`fts_doc_chunks`) indexing chunk headings, company names, and filing text.
   - Uses `websearch_to_tsquery('english', query)` to support natural language operators, boolean terms, and exact phrase matching (`ts_rank_cd`).

3. **Reciprocal Rank Fusion (RRF)**:
   - Combines vector rank ($R_{\text{vector}}$) and keyword rank ($R_{\text{text}}$) for each candidate document $d$:
     $$\text{RRF Score}(d) = \frac{1}{k + R_{\text{vector}}(d)} + \frac{1}{k + R_{\text{text}}(d)} \quad (k = 60)$$
   - The smoothing constant $k=60$ prevents top-ranked outliers from either method from dominating the candidate pool.

4. **Window Neighbor Expansion**:
   - For the top $N$ fused passages, the retriever inspects `prev_chunk_id` and `next_chunk_id` to retrieve preceding and succeeding narrative context. Table headers and MD&A commentary surrounding a financial figure are never severed.

---

## 4. Multi-Turn Conversational Memory & Ticker Inheritance

The conversational state machine maintains thread history without unbounded token bloating:

1. **Thread Windowing (`chats.py`)**:
   - Queries the last 6 messages (`LIMIT 6`) from Supabase `messages` ordered chronologically.
   - Injected into the PydanticAI system prompt under `--- PRIOR CONVERSATION HISTORY ---`.

2. **Active Ticker Heuristic & Inheritance (`orchestrator.py`)**:
   - The user query is scanned for ticker symbols and company aliases (`AAPL`, `Apple`, `NVIDIA`, etc.).
   - **Inheritance Rule**: If a user asks a follow-up omitting the company name (e.g., *"How did that compare to 2023?"* or *"What drove cloud margin expansion?"*), the system scans prior conversation turns, identifies the active subject ticker, and applies it to the retrieval filter.
   - Multi-company queries leave the ticker filter `None` to trigger cross-corpus retrieval across all 5 issuers.

---

## 5. PydanticAI Agent & LLM Reasoning

The reasoning core is built with **PydanticAI v2.52.0**, guaranteeing strict type safety and structured JSON outputs:

- **Primary Model**: Google `gemini-3-flash-preview` via Google AI Studio.
- **Dynamic Failover**: If Gemini 3 encounters high demand (HTTP 503 or 429), the orchestrator cascades to `gemini-2.5-flash` or `gemini-2.0-flash-lite`.
- **Dynamic Tool Execution**:
  - `search_filings(query, ticker, fiscal_year, top_n)`: Executes supplementary searches if pre-retrieved passages lack details.
  - `read_chunk(chunk_id)`: Fetches full uncompressed chunk context by UUID.
- **Output Schema (`GroundedAnswer`)**:
  - `answer`: Markdown response with mandatory in-line citation indicators (`[^1]`, `[^2]`).
  - `citations`: List of `CitationItem` objects (`chunk_id`, `citation_label`, `ticker`, `fiscal_year`, `section`, `snippet`).
  - `has_sufficient_evidence`: Boolean flag indicating if corpus supported the answer.
  - `refusal_reason`: Optional string for scope refusals.

---

## 6. The 4-Gate Fail-Closed Grounding Validator

Meridian Research's compliance contract enforces **zero hallucination tolerance**. Before any model output is presented to the user, `GroundingValidator` executes four mandatory gates:

```
[ Model Output: GroundedAnswer ]
       ├── Gate 1: UUID Provenance Check
       │   └── Does chunk_id exist in deps.all_retrieved_passages?
       ├── Gate 2: Entity / Ticker Integrity
       │   └── Does claimed ticker match passage.ticker?
       ├── Gate 3: Footnote Marker Synchronization
       │   └── Does regex r'\[\^(\d+)\]' in text match verified labels?
       └── Gate 4: Verbatim Lexical Snippet Verification
           └── Does the snippet exist verbatim in the chunk text?
```

1. **Gate 1 (UUID Provenance)**: Rejects any citation referencing a hallucinated or non-retrieved UUID.
2. **Gate 2 (Entity Consistency)**: Flags cross-company attribution errors (e.g., attributing Azure growth to Apple).
3. **Gate 3 (Footnote Synchronization)**: Uses regex `r"\[\^(\d+)\]"` to detect orphan footnote markers in text that lack matching `CitationItem` objects.
4. **Gate 4 (Lexical Verbatim Overlap)**: Verifies that the cited numeric snippet exists verbatim inside the source chunk text.
5. **Fail-Closed Policy**: If strict validation fails, ungrounded claims are flagged with visual alert warnings in the UI.

---

## 7. Scope Boundaries & Query Classification

Queries are classified into four mutually exclusive categories in `instructions.md`:

| Category | Query Type | System Behavior |
| :--- | :--- | :--- |
| **Category A: Trading Advice** | *"Should I buy Apple stock?"*, *"What is your NVDA target?"* | **Strict Refusal**: State compliance disclaimer (*"I cannot provide trading recommendations, buy/sell ratings, or price targets..."*). |
| **Category B: Out-of-Universe** | *"What was Tesla's gross margin?"*, *"Summarize Netflix"* | **Boundary Notice**: Inform user coverage is limited to AAPL, AMZN, GOOGL, MSFT, and NVDA. Offer coverage lookup. |
| **Category C: Finance Concepts** | *"What is capital budgeting?"*, *"Explain EBITDA vs Operating Income"* | **Educational Bridge**: Provide rigorous corporate finance definition, explain how it appears in 10-Ks (e.g., CapEx in Cash Flow Statement / MD&A), and offer coverage company lookup. |
| **Category D: Non-Financial** | *"Who was Napoleon?"*, *"What are symptoms of clinical depression?"* | **Domain Refusal**: State specialization in equity research and 10-K analysis; decline non-financial topics; prompt for finance questions. |

---

## 8. Full End-to-End Turn Execution Flow

```
1. User submits question via React UI
2. Frontend sends HTTP POST with thread_id to FastAPI /api/chat
3. Orchestrator extracts ticker & fiscal year (or inherits from thread history)
4. Hybrid Retriever executes dense vector + FTS search, applies RRF (k=60), expands neighbor chunks
5. PydanticAI Gemini agent runs with injected context & instructions
6. GroundingValidator executes 4-Gate verification on candidate answer
7. SSE Stream transmits real-time events to client:
   - 2:[{"type": "status", "stage": "searching"}]
   - 2:[{"type": "status", "stage": "reasoning"}]
   - 2:[{"type": "status", "stage": "validating"}]
   - 0:"Token stream chunks..."
   - 2:[{"type": "citations", "citations": [...]}]
   - 2:[{"type": "thread_title", "title": "..."}]
   - d:{"finishReason": "stop"}
8. Frontend renders markdown text, dynamic citation badges, and populates Citation Drawer
```

---

## 9. Infrastructure & Zero-Cost Cloud Deployment

The entire system is deployed in production at **$0.00 / month**:

- **Frontend**: Hosted on **Vercel Edge Network** (`document-assistant-black.vercel.app`). Automatically builds from GitHub `main`.
- **Backend API**: Hosted on **Render Free Web Service** (`document-assistant-backend-om3b.onrender.com`). Dockerless Python 3.13 running `uvicorn app.main:app` via lightweight `uv` (<80MB container).
- **Database & Vectors**: Hosted on **Supabase Free Tier** (PostgreSQL 15 + pgvector + Auth + Row Level Security).
- **LLM & Embeddings**: Hosted on **Google AI Studio Free Tier** (`gemini-3-flash-preview` + `gemini-embedding-001` with automated multi-key rotation).
- **Automated Test Suite**: 60 unit and integration tests passing (`pytest backend/tests`).
