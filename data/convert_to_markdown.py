"""Convert downloaded SEC HTML filings to Markdown using Docling + SEC Table Cleaner.

Preserves the exact directory structure (by year) and produces an updated
manifest.json in data/markdown/.
"""

import argparse
import json
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from docling.document_converter import DocumentConverter

# Add backend directory to path to import sec_table_cleaner
DATA_DIR = Path(__file__).resolve().parent
ROOT_DIR = DATA_DIR.parent
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from ingest.sec_table_cleaner import clean_sec_html

DOWNLOADS_DIR = DATA_DIR / "downloads"
MARKDOWN_DIR = DATA_DIR / "markdown"
INPUT_MANIFEST = DOWNLOADS_DIR / "manifest.json"
OUTPUT_MANIFEST = MARKDOWN_DIR / "manifest.json"


def convert_all(
    overwrite: bool = True,
    ticker: str | None = None,
    year: int | None = None,
    limit: int | None = None,
) -> None:
    if not INPUT_MANIFEST.exists():
        raise FileNotFoundError(f"Downloads manifest not found at: {INPUT_MANIFEST}")

    with open(INPUT_MANIFEST, encoding="utf-8") as f:
        manifest_data = json.load(f)

    filings = manifest_data.get("filings", [])
    if ticker:
        filings = [f for f in filings if f.get("ticker", "").upper() == ticker.upper()]
    if year:
        filings = [f for f in filings if str(year) in f.get("local_path", "") or f.get("filing_date", "").startswith(str(year))]
    if limit:
        filings = filings[:limit]

    total = len(filings)
    print(f"Found {total} filings to convert from {DOWNLOADS_DIR}...")

    MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
    converter = DocumentConverter()

    converted_filings = []
    start_total = time.time()

    for idx, filing in enumerate(filings, start=1):
        rel_html_path = filing.get("local_path")
        if not rel_html_path:
            continue

        input_file = DOWNLOADS_DIR / rel_html_path
        if not input_file.exists():
            print(f"[{idx}/{total}] WARNING: Source file missing: {input_file}")
            continue

        rel_md_path = str(Path(rel_html_path).with_suffix(".md"))
        output_file = MARKDOWN_DIR / rel_md_path
        output_file.parent.mkdir(parents=True, exist_ok=True)

        print(
            f"[{idx}/{total}] Converting {rel_html_path} ({input_file.stat().st_size / 1024:.1f} KB)...",
            end="",
            flush=True,
        )

        t0 = time.time()
        if not overwrite and output_file.exists():
            print(" (skipped, already exists)")
            char_count = output_file.stat().st_size
        else:
            with open(input_file, "r", encoding="utf-8", errors="ignore") as in_f:
                raw_html = in_f.read()

            # Pre-clean SEC tables into clean semantic tables
            cleaned_html = clean_sec_html(raw_html)

            with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tmp:
                tmp.write(cleaned_html)
                tmp_path = tmp.name

            try:
                result = converter.convert(tmp_path)
                md_content = result.document.export_to_markdown()
            finally:
                Path(tmp_path).unlink(missing_ok=True)

            with open(output_file, "w", encoding="utf-8") as out:
                out.write(md_content)

            elapsed = time.time() - t0
            char_count = len(md_content)
            print(f" Done in {elapsed:.2f}s ({char_count:,} chars)")

        updated_filing = dict(filing)
        updated_filing["local_path"] = rel_md_path
        updated_filing["html_path"] = rel_html_path
        updated_filing["markdown_chars"] = char_count
        converted_filings.append(updated_filing)

    # Write updated manifest.json to data/markdown/ if running across all filings
    if not ticker and not year and not limit:
        output_manifest_data = dict(manifest_data)
        output_manifest_data["format"] = "markdown"
        output_manifest_data["converted_at_utc"] = datetime.now(UTC).isoformat()
        output_manifest_data["converted_count"] = len(converted_filings)
        output_manifest_data["filings"] = converted_filings

        with open(OUTPUT_MANIFEST, "w", encoding="utf-8") as out_m:
            json.dump(output_manifest_data, out_m, indent=2)

        print(f"Manifest written to: {OUTPUT_MANIFEST}")

    total_elapsed = time.time() - start_total
    print(
        f"\nAll {len(converted_filings)} filings converted in {total_elapsed:.1f}s!"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert SEC HTML filings to clean Markdown")
    parser.add_argument("--ticker", type=str, help="Convert only for a specific ticker (e.g. AAPL)")
    parser.add_argument("--year", type=int, help="Convert only for a specific year (e.g. 2024)")
    parser.add_argument("--limit", type=int, help="Convert at most N filings")
    parser.add_argument("--no-overwrite", action="store_true", help="Skip already converted files")
    args = parser.parse_args()

    convert_all(
        overwrite=not args.no_overwrite,
        ticker=args.ticker,
        year=args.year,
        limit=args.limit,
    )
