"""Dedicated SEC EDGAR HTML Table Normalizer.

Transforms nested, spacer-bloated SEC EDGAR HTML tables into clean,
semantic HTML tables optimized for Docling markdown export, RAG chunking,
and senior equity research analyst readability.
"""

import re
import warnings
from typing import Any
from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Regex to detect tabular financial data (numbers with commas, percentages, currency)
FINANCIAL_DATA_PATTERN = re.compile(
    r"\b\d{1,3}(,\d{3})+\b|"  # e.g. 201,183 or 1,234,567
    r"\$\s*\d+|"              # e.g. $201 or $ 201
    r"\b\d+\.?\d*%\b|"        # e.g. 13% or 13.5%
    r"\(\d{1,3}(,\d{3})*\)"   # e.g. (2,847) negative numbers
)

CURRENCY_SYMBOLS = ("$", "€", "£", "¥")


def _clean_cell_text(text: str) -> str:
    """Normalize cell whitespace, non-breaking spaces, and unicode dashes."""
    t = text.replace("\xa0", " ").replace("\u200b", "").strip()
    t = re.sub(r"\s+", " ", t)
    if t in ("—", "–", "- -", "— —"):
        return "—"
    return t


def _merge_split_cells(raw_cells: list[str]) -> list[str]:
    """Merge split currency symbols, percentages, and negative parentheses into single cells."""
    merged: list[str] = []
    i = 0
    n = len(raw_cells)

    while i < n:
        val = raw_cells[i]

        # 1. Currency symbol followed by number
        if val in CURRENCY_SYMBOLS and i + 1 < n:
            next_val = raw_cells[i + 1]
            if re.match(r"^[\(\d—\-]", next_val):
                merged.append(val + next_val)
                i += 2
                continue
            else:
                merged.append(val)

        # 2. Percentage sign attached to previous number
        elif val == "%" and merged:
            merged[-1] = merged[-1] + "%"

        # 3. Closing parenthesis or )% attached to previous number
        elif val in (")", ")%") and merged and not merged[-1].endswith(")"):
            merged[-1] = merged[-1] + val

        # 4. Multiplier / pts notation attached to previous number
        elif val in ("pts", "pts.", "bps") and merged:
            merged[-1] = merged[-1] + " " + val

        # 5. Up / Down directional indicator followed by number or percentage
        elif val in ("Up", "Down") and i + 1 < n and re.match(r"^[\d\.\+\-\(]", raw_cells[i + 1]):
            merged.append(f"{val} {raw_cells[i + 1]}")
            i += 2
            continue

        else:
            merged.append(val)

        i += 1

    return merged


def clean_sec_table(table_tag: Tag, soup: BeautifulSoup) -> Tag | None:
    """Normalize an individual SEC table element.

    Returns:
        - Clean semantic <table> tag if table contains financial data
        - Clean <p> tag if table is a non-tabular narrative block
        - None if table is empty layout or visual spacing
    """
    rows = table_tag.find_all("tr")
    if not rows or len(rows) < 2:
        return None

    all_text = table_tag.get_text()
    has_numbers = bool(FINANCIAL_DATA_PATTERN.search(all_text))

    # If table has no numbers, check if it is meaningful text (e.g. signature or note)
    if not has_numbers:
        plain_text = _clean_cell_text(all_text)
        if len(plain_text) > 30 and not plain_text.startswith("Table of Contents"):
            p_tag = soup.new_tag("p")
            p_tag.string = plain_text
            return p_tag
        return None

    cleaned_rows: list[list[str]] = []

    for r in rows:
        cells = r.find_all(["td", "th"])
        raw_cell_texts = []
        for c in cells:
            t = _clean_cell_text(c.get_text())
            if t:
                raw_cell_texts.append(t)

        if not raw_cell_texts:
            continue

        merged_row = _merge_split_cells(raw_cell_texts)
        if merged_row:
            cleaned_rows.append(merged_row)

    if len(cleaned_rows) < 2:
        return None

    data_row_lengths = [len(r) for r in cleaned_rows if len(r) > 1]
    if not data_row_lengths:
        return None
    max_cols = max(data_row_lengths)
    if max_cols < 2:
        return None

    clean_table = soup.new_tag("table")
    clean_table["border"] = "1"
    thead = soup.new_tag("thead")
    clean_table.append(thead)

    header = cleaned_rows[0]

    header_idx = 0
    if len(header) < 3 and len(cleaned_rows) > 2 and len(cleaned_rows[1]) >= 2:
        r1_text = " ".join(cleaned_rows[1])
        if re.search(r"\b202[0-5]\b|\bJan|\bFeb|\bMar|\bSep|\bDec", r1_text):
            header = cleaned_rows[1]
            header_idx = 1

    header_row_tag = soup.new_tag("tr")
    if len(header) < max_cols:
        header = ["Description"] + header + [""] * (max_cols - len(header) - 1)
    else:
        header = header + [""] * (max_cols - len(header))

    for h in header:
        th = soup.new_tag("th")
        th.string = h
        header_row_tag.append(th)
    thead.append(header_row_tag)

    tbody = soup.new_tag("tbody")
    clean_table.append(tbody)

    for r in cleaned_rows[header_idx + 1:]:
        tr = soup.new_tag("tr")
        if len(r) == 1:
            td = soup.new_tag("td")
            b = soup.new_tag("strong")
            b.string = r[0]
            td.append(b)
            td["colspan"] = str(max_cols)
            tr.append(td)
        else:
            padded = r + [""] * (max_cols - len(r))
            for item in padded:
                td = soup.new_tag("td")
                td.string = item
                tr.append(td)
        tbody.append(tr)

    return clean_table


def clean_sec_html(html_content: str) -> str:
    """Pre-process SEC EDGAR HTML to normalize tables and eliminate layout bloat.

    Args:
        html_content: Raw SEC HTML filing text.

    Returns:
        Sanitized HTML string ready for Docling document conversion.
    """
    soup = BeautifulSoup(html_content, "lxml")

    # 1. Fix letter-spacing kerning artifacts (e.g. "INC OME STATEMENTS")
    for span in soup.find_all("span", style=re.compile(r"letter-spacing", re.IGNORECASE)):
        txt = span.get_text()
        if txt and re.match(r"^([A-Za-z]\s+)+[A-Za-z]$", txt.strip()):
            span.string = txt.replace(" ", "")

    # 2. Process all table tags
    tables = soup.find_all("table")
    for t in tables:
        cleaned = clean_sec_table(t, soup)
        if cleaned is not None:
            t.replace_with(cleaned)
        else:
            t.decompose()

    return str(soup)
