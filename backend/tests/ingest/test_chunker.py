"""Unit tests for document chunking and local embeddings."""

from pathlib import Path
import pytest
from ingest.chunker import DocumentChunker, OpenAITiktokenTokenizer
from ingest.embedder import LocalEmbedder


def test_tokenizer_token_counting() -> None:
    """Verify tiktoken accurately counts tokens."""
    tokenizer = OpenAITiktokenTokenizer(max_tokens=800)
    assert tokenizer.count_tokens("") == 0
    assert tokenizer.count_tokens("Hello world") == 2
    assert tokenizer.get_max_tokens() == 800


def test_chunker_empty_file(tmp_path: Path) -> None:
    """Empty file should produce zero chunks without error."""
    empty_file = tmp_path / "empty.md"
    empty_file.write_text("", encoding="utf-8")

    chunker = DocumentChunker(max_tokens=800)
    chunks = chunker.chunk_file(empty_file)
    assert chunks == []


def test_chunker_deduplication(tmp_path: Path) -> None:
    """Duplicate text passages should be deduplicated."""
    test_file = tmp_path / "duplicates.md"
    content = """# Item 1. Business

Apple manufactures smartphones and consumer electronics.

Apple manufactures smartphones and consumer electronics.
"""
    test_file.write_text(content, encoding="utf-8")

    chunker = DocumentChunker(max_tokens=800)
    chunks = chunker.chunk_file(test_file)

    # Should only produce one unique chunk for the repeated sentence
    chunk_texts = [c["chunk_text"].strip() for c in chunks]
    assert len(chunk_texts) == len(set(chunk_texts))


def test_chunker_metadata_and_tables(tmp_path: Path) -> None:
    """Headings and table detection metadata should be attached to chunks."""
    test_file = tmp_path / "sample.md"
    content = """# Item 1. Business

General description of operations and supply chain.

## Revenue Breakdown

| Segment | Revenue |
| :--- | :--- |
| Products | B |
| Services | B |
"""
    test_file.write_text(content, encoding="utf-8")

    chunker = DocumentChunker(max_tokens=800)
    doc_meta = {"ticker": "AAPL", "fiscal_year": 2024}
    chunks = chunker.chunk_file(test_file, doc_meta=doc_meta)

    assert len(chunks) >= 2
    for c in chunks:
        assert c["metadata"]["ticker"] == "AAPL"
        assert c["metadata"]["fiscal_year"] == 2024
        assert c["token_count"] > 0
        assert c["token_count"] <= 800

    # At least one chunk should be flagged as containing a table
    table_chunks = [c for c in chunks if c["metadata"].get("is_table")]
    assert len(table_chunks) >= 1


def test_local_embedder_dimensions() -> None:
    """Local BGE model should produce exactly 768-dimensional normalized vectors."""
    embedder = LocalEmbedder()
    vec = embedder.embed_text("Apple net sales for fiscal year 2024.")
    assert len(vec) == 768
    assert all(isinstance(x, float) for x in vec)

    # Test batch embedding
    batch = embedder.embed_batch(["Text A", "Text B"])
    assert len(batch) == 2
    assert len(batch[0]) == 768
    assert len(batch[1]) == 768
