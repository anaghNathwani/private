"""
pdf_parser.py — Extract a 9x9 Sudoku grid from a PDF file.

Supports two extraction strategies:
  1. Table extraction (pdfplumber.page.extract_tables)
  2. Text-line parsing (space/comma/pipe-separated digit rows)

Empty cells may be represented as: 0, ., _, or blank.
"""

import re
import pdfplumber


def extract_grid(pdf_path: str) -> list[list[int]]:
    """
    Open the PDF at pdf_path and return a 9x9 grid of ints.
    Empty cells are represented as 0.

    Raises:
        FileNotFoundError: if the PDF file does not exist.
        ValueError: if no valid 9x9 Sudoku grid can be found.
    """
    try:
        pdf = pdfplumber.open(pdf_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    except Exception as exc:
        raise ValueError(f"Could not open PDF '{pdf_path}': {exc}") from exc

    with pdf:
        for page in pdf.pages:
            # Strategy 1: table extraction
            grid = _try_table_extraction(page)
            if grid is not None:
                _validate(grid)
                return grid

            # Strategy 2: text-line parsing
            text = page.extract_text() or ""
            grid = _try_text_parsing(text)
            if grid is not None:
                _validate(grid)
                return grid

    raise ValueError(
        "Could not find a 9x9 Sudoku grid in the PDF. "
        "Ensure the puzzle is represented as a text table or 9 rows of 9 digits."
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cell_to_int(cell: str | None) -> int | None:
    """Convert a raw cell string to an int (0 for empty). Returns None on error."""
    if cell is None:
        return 0
    cell = cell.strip()
    if cell in ("", ".", "_", "0"):
        return 0
    if cell.isdigit() and 1 <= int(cell) <= 9:
        return int(cell)
    return None


def _try_table_extraction(page) -> list[list[int]] | None:
    """Attempt to find a 9x9 table on the page."""
    try:
        tables = page.extract_tables()
    except Exception:
        return None

    for table in tables:
        if len(table) != 9:
            continue
        grid = []
        valid = True
        for row in table:
            # Filter out None separators that pdfplumber sometimes inserts
            cells = [c for c in row if c is not None or True]
            # Some extractions include extra blank columns; strip them
            parsed = []
            for cell in row:
                val = _cell_to_int(cell)
                if val is None:
                    valid = False
                    break
                parsed.append(val)
            if not valid:
                break
            if len(parsed) != 9:
                valid = False
                break
            grid.append(parsed)
        if valid and len(grid) == 9:
            return grid
    return None


# Pattern: a row of exactly 9 tokens that are digits (1-9) or empty markers
_EMPTY_MARKERS = {"0", ".", "_"}
_TOKEN_RE = re.compile(r"[1-9]|[._0]")


def _try_text_parsing(text: str) -> list[list[int]] | None:
    """
    Scan lines of text for 9-token rows that form a valid Sudoku grid.

    Accepted formats:
      5 3 . . 7 . . . .
      5,3,0,0,7,0,0,0,0
      5|3|0|0|7|0|0|0|0
      530070000  (9 consecutive digits/dots with no spaces)
    """
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = _parse_line(line)
        if parsed is not None:
            rows.append(parsed)
            if len(rows) == 9:
                return rows
        else:
            # Reset if we hit a non-grid line after starting
            if rows:
                rows = []

    # Allow trailing non-grid lines — return if we collected exactly 9
    if len(rows) == 9:
        return rows
    return None


def _parse_line(line: str) -> list[int] | None:
    """
    Try to interpret a single text line as one row of 9 Sudoku cells.
    Returns a list of 9 ints, or None if the line doesn't match.
    """
    # Remove common decorators: pipes, dashes, plus signs used as grid borders
    if re.fullmatch(r"[-+|=\s]+", line):
        return None

    # Try splitting by common delimiters: whitespace, comma, pipe
    for sep in (None, ",", "|"):
        tokens = line.split(sep) if sep else line.split()
        tokens = [t.strip() for t in tokens if t.strip()]
        # Filter out pipe-only separator tokens
        tokens = [t for t in tokens if not re.fullmatch(r"[-+|]+", t)]
        if len(tokens) == 9:
            row = []
            for t in tokens:
                if t in _EMPTY_MARKERS:
                    row.append(0)
                elif t.isdigit() and 1 <= int(t) <= 9:
                    row.append(int(t))
                else:
                    break
            else:
                return row

    # Try a 9-character run of digits/dots (no spaces)
    compact = re.sub(r"\s+", "", line)
    if len(compact) == 9 and re.fullmatch(r"[0-9.]+", compact):
        row = []
        for ch in compact:
            row.append(0 if ch in _EMPTY_MARKERS else int(ch))
        return row

    return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate(grid: list[list[int]]) -> None:
    """
    Confirm the grid is 9x9, values 0-9, and no pre-filled digit appears
    twice in any row, column, or 3x3 box.

    Raises ValueError with a descriptive message on failure.
    """
    if len(grid) != 9:
        raise ValueError(f"Grid has {len(grid)} rows, expected 9.")
    for r, row in enumerate(grid):
        if len(row) != 9:
            raise ValueError(f"Row {r+1} has {len(row)} cells, expected 9.")
        for val in row:
            if not (0 <= val <= 9):
                raise ValueError(f"Invalid cell value {val} at row {r+1}.")

    # Check rows
    for r in range(9):
        seen = [v for v in grid[r] if v != 0]
        if len(seen) != len(set(seen)):
            raise ValueError(f"Duplicate value in row {r+1}.")

    # Check columns
    for c in range(9):
        seen = [grid[r][c] for r in range(9) if grid[r][c] != 0]
        if len(seen) != len(set(seen)):
            raise ValueError(f"Duplicate value in column {c+1}.")

    # Check 3x3 boxes
    for br in range(3):
        for bc in range(3):
            seen = []
            for r in range(br * 3, br * 3 + 3):
                for c in range(bc * 3, bc * 3 + 3):
                    if grid[r][c] != 0:
                        seen.append(grid[r][c])
            if len(seen) != len(set(seen)):
                raise ValueError(
                    f"Duplicate value in 3x3 box at rows {br*3+1}-{br*3+3}, "
                    f"cols {bc*3+1}-{bc*3+3}."
                )
