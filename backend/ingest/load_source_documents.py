"""Load normalized Markdown SEC filings into Supabase source_documents table."""

import json
import time
from pathlib import Path
from typing import Any

from app.database.supabase import get_service_role_client

# Map of supported tickers to full corporate names
COMPANY_NAMES: dict[str, str] = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
}

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
MARKDOWN_DIR = ROOT_DIR / "data" / "markdown"
MANIFEST_PATH = MARKDOWN_DIR / "manifest.json"


def load_source_documents() -> list[dict[str, Any]]:
    """Read data/markdown/manifest.json and upsert each filing into source_documents."""
    if not MANIFEST_PATH.exists():
        msg = f"Markdown manifest not found at: {MANIFEST_PATH}"
        raise FileNotFoundError(msg)

    with open(MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)

    filings = manifest.get("filings", [])
    total = len(filings)
    print(f"Loading {total} filings from {MARKDOWN_DIR} into Supabase source_documents...")

    client = get_service_role_client()
    loaded_records: list[dict[str, Any]] = []
    start_time = time.time()

    for idx, filing in enumerate(filings, start=1):
        rel_path = filing.get("local_path")
        if not rel_path:
            continue

        file_path = MARKDOWN_DIR / rel_path
        if not file_path.exists():
            print(f"[{idx}/{total}] WARNING: File not found: {file_path}")
            continue

        with open(file_path, encoding="utf-8") as f_md:
            content_md = f_md.read()

        ticker = filing.get("ticker", "UNKNOWN")
        company_name = COMPANY_NAMES.get(ticker, ticker)
        filing_type = filing.get("form", "10-K")
        filing_date = filing.get("filing_date", "")
        report_date = filing.get("report_date", filing_date)
        accession_number = filing.get("accession_number", "")
        source_url = filing.get("source_url", "")

        # Derive fiscal year from report date or filing date
        fiscal_year = int(report_date[:4]) if report_date and len(report_date) >= 4 else 2024

        metadata = {
            "cik": filing.get("cik"),
            "report_date": report_date,
            "primary_document": filing.get("primary_document"),
            "html_path": filing.get("html_path"),
            "markdown_path": rel_path,
            "markdown_chars": len(content_md),
        }

        payload: dict[str, Any] = {
            "ticker": ticker,
            "company_name": company_name,
            "filing_type": filing_type,
            "filing_date": filing_date,
            "fiscal_year": fiscal_year,
            "accession_number": accession_number,
            "source_url": source_url,
            "content_md": content_md,
            "metadata": metadata,
        }

        t0 = time.time()
        print(
            f"[{idx}/{total}] Upserting {ticker} ({fiscal_year} {filing_type}) "
            f"[{accession_number}] ({len(content_md):,} chars)...",
            end="",
            flush=True,
        )

        response = (
            client.table("source_documents")
            .upsert(payload, on_conflict="accession_number")
            .execute()
        )

        elapsed = time.time() - t0
        if response.data:
            loaded_records.append(response.data[0])
            print(f" Done in {elapsed:.2f}s (ID: {response.data[0].get('id')})")
        else:
            print(f" Done in {elapsed:.2f}s")

    total_time = time.time() - start_time
    print(f"\nSuccessfully loaded {len(loaded_records)}/{total} source documents in {total_time:.1f}s.")

    # Verification query
    count_response = client.table("source_documents").select("id", count="exact").execute()
    print(f"Total rows in source_documents table: {count_response.count}")

    return loaded_records


if __name__ == "__main__":
    load_source_documents()
