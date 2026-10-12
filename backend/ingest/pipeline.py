"""End-to-end ingestion pipeline: chunking, embedding, and Supabase insertion."""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any

from app.database.supabase import get_service_role_client
from ingest.chunker import DocumentChunker
from ingest.embedder import LocalEmbedder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingest.pipeline")

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
MARKDOWN_DIR = ROOT_DIR / "data" / "markdown"


def run_pipeline(
    test_one: bool = False,
    ticker: str | None = None,
    limit: int | None = None,
    force: bool = False,
) -> None:
    """Run ingestion pipeline across source documents."""
    supabase = get_service_role_client()
    chunker = DocumentChunker(max_tokens=800)
    embedder = LocalEmbedder()

    # 1. Fetch source documents from Supabase
    query = supabase.table("source_documents").select("id, ticker, company_name, fiscal_year, filing_type, accession_number, metadata")
    if ticker:
        query = query.eq("ticker", ticker.upper())
    # Order so AAPL 2024 is prioritized for deterministic testing
    query = query.order("ticker").order("fiscal_year", desc=True)

    if test_one:
        query = query.limit(1)
    elif limit:
        query = query.limit(limit)

    res = query.execute()
    docs = res.data or []

    if not docs:
        logger.error("No source documents found in database matching criteria.")
        return

    logger.info("Found %d source documents to process.", len(docs))

    total_chunks_inserted = 0
    start_time = time.time()

    for idx, doc in enumerate(docs, 1):
        doc_id = doc["id"]
        doc_ticker = doc["ticker"]
        year = doc["fiscal_year"]
        acc_num = doc["accession_number"]
        meta = doc.get("metadata") or {}
        rel_path = meta.get("markdown_path")

        if not rel_path:
            logger.warning("Skipping doc %s (%s %d): missing markdown_path in metadata", doc_id, doc_ticker, year)
            continue

        file_path = MARKDOWN_DIR / rel_path
        if not file_path.exists():
            logger.warning("Markdown file does not exist on disk: %s", file_path)
            continue

        # 2. Check if chunks already exist for this document (idempotency)
        existing_chunks = (
            supabase.table("document_chunks")
            .select("id", count="exact")
            .eq("document_id", doc_id)
            .limit(1)
            .execute()
        )
        existing_count = existing_chunks.count or 0

        if existing_count > 0:
            if force:
                logger.info("Force flag set: deleting %d existing chunks for %s (%s %d)", existing_count, acc_num, doc_ticker, year)
                supabase.table("document_chunks").delete().eq("document_id", doc_id).execute()
            else:
                logger.info("Skipping already ingested document %s (%s %d): %d chunks exist", acc_num, doc_ticker, year, existing_count)
                continue

        logger.info("[%d/%d] Processing %s %d (%s)...", idx, len(docs), doc_ticker, year, file_path.name)

        # 3. Chunk the document
        doc_meta = {
            "ticker": doc_ticker,
            "company_name": doc.get("company_name"),
            "fiscal_year": year,
            "filing_type": doc.get("filing_type"),
            "accession_number": acc_num,
        }
        chunks = chunker.chunk_file(file_path, doc_meta=doc_meta)

        if not chunks:
            logger.warning("No chunks generated for %s", file_path.name)
            continue

        # 4. Handle --test-one mode
        if test_one:
            logger.info("=== PRE-FLIGHT TEST-ONE MODE ACTIVATED ===")
            logger.info("Total chunks generated from file: %d", len(chunks))
            logger.info("Selecting ONLY Chunk 0 to verify embedding and Supabase insertion...")

            test_chunk = chunks[0]
            logger.info("Embedding Chunk 0 text (%d tokens)...", test_chunk["token_count"])
            emb = embedder.embed_text(test_chunk["chunk_text"])
            logger.info("Generated embedding vector: %d dimensions", len(emb))

            row_data = {
                "document_id": doc_id,
                "chunk_index": test_chunk["chunk_index"],
                "chunk_text": test_chunk["chunk_text"],
                "token_count": test_chunk["token_count"],
                "embedding": emb,
                "metadata": test_chunk["metadata"],
            }

            insert_res = supabase.table("document_chunks").insert(row_data).execute()
            if not insert_res.data:
                logger.error("Failed to insert test chunk into Supabase.")
                sys.exit(1)

            created_id = insert_res.data[0]["id"]
            logger.info("Successfully inserted test chunk! Row ID: %s", created_id)

            # 5. Verification query back from Supabase
            verify_res = (
                supabase.table("document_chunks")
                .select("id, document_id, chunk_index, token_count, metadata, created_at")
                .eq("id", created_id)
                .single()
                .execute()
            )

            logger.info("=== VERIFICATION QUERY RESULTS ===")
            logger.info("Record ID:       %s", verify_res.data.get("id"))
            logger.info("Document ID:     %s", verify_res.data.get("document_id"))
            logger.info("Chunk Index:     %s", verify_res.data.get("chunk_index"))
            logger.info("Token Count:     %s", verify_res.data.get("token_count"))
            logger.info("Metadata:        %s", verify_res.data.get("metadata"))
            logger.info("Chunk Preview:   %s...", " ".join(test_chunk["chunk_text"][:140].split()))
            logger.info("Status:          PASSED - Pre-flight test successfully verified in Supabase!")
            return

        # 5. Full run: Batch embeddings
        texts = [c["chunk_text"] for c in chunks]
        logger.info("Generating embeddings for %d chunks in batches...", len(texts))
        embeddings = embedder.embed_batch(texts, batch_size=50)

        # 6. Batch insert into Supabase
        db_rows: list[dict[str, Any]] = []
        for c, emb in zip(chunks, embeddings, strict=True):
            db_rows.append(
                {
                    "document_id": doc_id,
                    "chunk_index": c["chunk_index"],
                    "chunk_text": c["chunk_text"],
                    "token_count": c["token_count"],
                    "embedding": emb,
                    "metadata": c["metadata"],
                }
            )

        # Insert in batches of 50
        batch_size = 50
        for b_idx in range(0, len(db_rows), batch_size):
            insert_batch = db_rows[b_idx : b_idx + batch_size]
            supabase.table("document_chunks").insert(insert_batch).execute()

        total_chunks_inserted += len(db_rows)
        logger.info("Inserted %d chunks for %s %d (running total: %d)", len(db_rows), doc_ticker, year, total_chunks_inserted)

    elapsed = time.time() - start_time
    logger.info("Ingestion finished in %.2fs. Total chunks inserted: %d", elapsed, total_chunks_inserted)


def main() -> None:
    parser = argparse.ArgumentParser(description="SEC Filing Chunker and Embedding Pipeline")
    parser.add_argument("--test-one", action="store_true", help="Run pre-flight test on 1 single chunk only")
    parser.add_argument("--ticker", type=str, help="Filter by company ticker (e.g. AAPL)")
    parser.add_argument("--limit", type=int, help="Limit number of documents to process")
    parser.add_argument("--force", action="store_true", help="Force re-chunking documents that already have chunks")
    args = parser.parse_args()

    run_pipeline(
        test_one=args.test_one,
        ticker=args.ticker,
        limit=args.limit,
        force=args.force,
    )


if __name__ == "__main__":
    main()
