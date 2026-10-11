"""Convert downloaded SEC HTML filings to Markdown using Docling.

Preserves the exact directory structure (by year) and produces an updated
manifest.json in data/markdown/.
"""

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from docling.document_converter import DocumentConverter

# Paths relative to this script
DATA_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = DATA_DIR / "downloads"
MARKDOWN_DIR = DATA_DIR / "markdown"
INPUT_MANIFEST = DOWNLOADS_DIR / "manifest.json"
OUTPUT_MANIFEST = MARKDOWN_DIR / "manifest.json"


def convert_all(overwrite: bool = True) -> None:
    if not INPUT_MANIFEST.exists():
        raise FileNotFoundError(f"Downloads manifest not found at: {INPUT_MANIFEST}")

    with open(INPUT_MANIFEST, encoding="utf-8") as f:
        manifest_data = json.load(f)

    filings = manifest_data.get("filings", [])
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
            result = converter.convert(input_file)
            md_content = result.document.export_to_markdown()

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

    # Write updated manifest.json to data/markdown/
    output_manifest_data = dict(manifest_data)
    output_manifest_data["format"] = "markdown"
    output_manifest_data["converted_at_utc"] = datetime.now(UTC).isoformat()
    output_manifest_data["converted_count"] = len(converted_filings)
    output_manifest_data["filings"] = converted_filings

    with open(OUTPUT_MANIFEST, "w", encoding="utf-8") as out_m:
        json.dump(output_manifest_data, out_m, indent=2)

    total_elapsed = time.time() - start_total
    print(
        f"\nAll {len(converted_filings)} filings converted in {total_elapsed:.1f}s!"
    )
    print(f"Manifest written to: {OUTPUT_MANIFEST}")


if __name__ == "__main__":
    convert_all(overwrite=True)
