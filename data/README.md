# Data — Document Assistant Corpus & Ingestion

This directory contains the SEC EDGAR 10-K filings corpus and the multi-stage conversion pipeline used by **Document Assistant**.

---

## Directory Structure

```text
data/
├── downloads/           # Raw SEC EDGAR .htm filings grouped by fiscal year (gitignored)
│   ├── 2021/
│   ├── 2022/
│   ├── 2023/
│   ├── 2024/
│   └── 2025/
├── markdown/            # Cleaned, standardized Markdown filings produced by Docling + Table Cleaner
│   ├── manifest.json    # Metadata registry for all 25 filings (tickers, dates, accessions)
│   ├── 2021/
│   ├── 2022/
│   ├── 2023/
│   ├── 2024/
│   └── 2025/
├── download.py          # Script to fetch SEC EDGAR 10-K filings from sec.gov
└── convert_to_markdown.py # Normalization pipeline: SEC Table Cleaner + Docling conversion
```

---

## Pipeline Workflow

1. **Download Raw Filings**:
   ```bash
   uv run python data/download.py
   ```
   Downloads 10-K filings for AAPL, MSFT, NVDA, AMZN, and GOOGL across fiscal years 2021–2025.

2. **Clean & Convert to Markdown**:
   ```bash
   uv run python data/convert_to_markdown.py
   ```
   - Applies `sec_table_cleaner.py` to strip 20–35 spacer layout columns and merge split currency signs, percentages, and negative parentheses into unified numeric cells.
   - Passes clean semantic HTML tables into Docling to produce high-density, pristine Markdown pipe tables.

3. **Ingest & Embed Chunks into Supabase**:
   ```bash
   uv run python backend/ingest/pipeline.py --force
   ```
   Chunks the Markdown filings (keeping tables intact inside single chunks), generates local BGE-768 embeddings, and writes to `document_chunks`.
