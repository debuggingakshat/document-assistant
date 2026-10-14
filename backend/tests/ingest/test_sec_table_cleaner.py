import pytest
from bs4 import BeautifulSoup
from ingest.sec_table_cleaner import (
    _merge_split_cells,
    clean_sec_table,
    clean_sec_html,
)


def test_merge_split_cells():
    raw = ["iPhone", "$", "201,183", "3", "%", "$", "200,583", "(2)", "%"]
    merged = _merge_split_cells(raw)
    assert merged == ["iPhone", "$201,183", "3%", "$200,583", "(2)%"]


def test_merge_directional_and_points():
    raw = ["Revenue", "$", "60,922", "Up", "126%", "Up", "15.8", "pts"]
    merged = _merge_split_cells(raw)
    assert merged == ["Revenue", "$60,922", "Up 126%", "Up 15.8 pts"]


def test_empty_layout_table_removed():
    soup = BeautifulSoup("<table><tr><td style='width:1%'></td></tr></table>", "lxml")
    t = soup.find("table")
    assert clean_sec_table(t, soup) is None


def test_financial_table_retains_rectangular_shape():
    html = """
    <table>
      <tr><td></td><td>2024</td><td>2023</td></tr>
      <tr><td>Services</td><td>$</td><td>96,169</td><td>$</td><td>85,200</td></tr>
      <tr><td>Total net sales</td><td>391,035</td><td>383,285</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, "lxml")
    clean = clean_sec_table(soup.find("table"), soup)
    assert clean is not None
    assert clean.name == "table"
    rows = clean.find_all("tr")
    assert len(rows) == 3
    # Check header has 3 columns: Description, 2024, 2023
    headers = [th.get_text() for th in rows[0].find_all("th")]
    assert headers == ["Description", "2024", "2023"]
    # Check data rows have 3 cells
    row1 = [td.get_text() for td in rows[1].find_all("td")]
    assert row1 == ["Services", "$96,169", "$85,200"]


def test_clean_sec_html_full_integration():
    html = """
    <html>
      <body>
        <h1>Apple Inc.</h1>
        <table><tr><td>Layout Spacer</td></tr></table>
        <table>
          <tr><td></td><td>2024</td></tr>
          <tr><td>iPhone</td><td>$</td><td>201,183</td></tr>
        </table>
      </body>
    </html>
    """
    cleaned_html = clean_sec_html(html)
    assert "Layout Spacer" in cleaned_html or "table" in cleaned_html
    assert "$201,183" in cleaned_html
