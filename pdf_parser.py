from __future__ import annotations

"""
pdf_parser.py — Extract a 9x9 Sudoku grid from a PDF file.

Three extraction strategies, tried in order:
  1. Table extraction   (pdfplumber — fast, works on PDF tables)
  2. Text-line parsing  (pdfplumber — works on text-based PDFs)
  3. OCR               (pdf2image + pytesseract — fallback for image-based PDFs)

Empty cells may be represented as: 0, ., _, or blank.
"""

import re
import pdfplumber

# OCR imports are deferred so the module still loads even if the libraries
# aren't installed; OCR is only attempted when strategies 1 & 2 both fail.
_OCR_AVAILABLE = True
try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image, ImageOps, ImageFilter
except ImportError:
    _OCR_AVAILABLE = False


def extract_grid(pdf_path: str) -> list[list[int]]:
    """
    Open the PDF at pdf_path and return a 9x9 grid of ints.
    Empty cells are represented as 0.

    Raises:
        FileNotFoundError: if the PDF file does not exist.
        ValueError: if no valid 9x9 Sudoku grid can be found.
    """
    import os
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Strategies 1 & 2: text-based extraction via pdfplumber
    text_error = None
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                grid = _try_table_extraction(page)
                if grid is not None:
                    print("  [parser] Strategy 1 (table extraction): success")
                    _validate(grid)
                    return grid

                text = page.extract_text() or ""
                grid = _try_text_parsing(text)
                if grid is not None:
                    print("  [parser] Strategy 2 (text parsing): success")
                    _validate(grid)
                    return grid

            print("  [parser] Strategy 1 & 2: no grid found in text/tables")
            if pdf.pages:
                sample = (pdf.pages[0].extract_text() or "")[:200].replace("\n", " ")
                print(f"  [parser] Page text sample: {sample!r}")
    except Exception as exc:
        text_error = exc
        print(f"  [parser] Strategy 1 & 2 error: {exc}")

    # Strategy 3: OCR fallback for image-based PDFs
    if _OCR_AVAILABLE:
        print("  [parser] Strategy 3 (OCR): starting…")
        grid = _try_ocr_extraction(pdf_path)
        if grid is not None:
            print("  [parser] Strategy 3 (OCR): success")
            _validate(grid)
            return grid
        print("  [parser] Strategy 3 (OCR): no grid found")
        raise ValueError(
            "Could not extract a Sudoku grid from the PDF.\n"
            "OCR was attempted but failed. Make sure the PDF contains a clear, "
            "printed Sudoku grid with no heavy graphical overlays."
        )

    raise ValueError(
        "Could not find a 9x9 Sudoku grid in the PDF. "
        "Ensure the puzzle is represented as a text table or 9 rows of 9 digits.\n"
        "(Install pdf2image and pytesseract to enable OCR for image-based PDFs.)"
    )


# ---------------------------------------------------------------------------
# Strategy 1 — pdfplumber table extraction
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


# ---------------------------------------------------------------------------
# Strategy 2 — text-line parsing
# ---------------------------------------------------------------------------

_EMPTY_MARKERS = {"0", ".", "_"}


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
            if rows:
                rows = []

    if len(rows) == 9:
        return rows
    return None


def _parse_line(line: str) -> list[int] | None:
    """Try to interpret a text line as one row of 9 Sudoku cells."""
    if re.fullmatch(r"[-+|=\s]+", line):
        return None

    for sep in (None, ",", "|"):
        tokens = line.split(sep) if sep else line.split()
        tokens = [t.strip() for t in tokens if t.strip()]
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

    compact = re.sub(r"\s+", "", line)
    if len(compact) == 9 and re.fullmatch(r"[0-9.]+", compact):
        row = []
        for ch in compact:
            row.append(0 if ch in _EMPTY_MARKERS else int(ch))
        return row

    return None


# ---------------------------------------------------------------------------
# Strategy 3 — OCR fallback
# ---------------------------------------------------------------------------

def _try_ocr_extraction(pdf_path: str) -> list[list[int]] | None:
    """Convert PDF pages to images and run OCR to find the Sudoku grid."""
    try:
        # 600 DPI gives sharper cell images — important for digit accuracy
        images = convert_from_path(pdf_path, dpi=600)
    except Exception:
        return None

    for image in images:
        # Try cell-by-cell first — more reliable than full-page for grid images
        grid = _ocr_cell_by_cell(image)
        if grid is not None:
            return grid
        grid = _ocr_full_page(image)
        if grid is not None:
            return grid

    return None


def _preprocess_cell(image: "Image.Image") -> "Image.Image":
    """
    Minimal preprocessing for a single cell image.
    Slight contrast boost only — heavy binarisation hurts thin strokes.
    """
    image = image.convert("RGB")
    image = ImageOps.autocontrast(image, cutoff=1)
    return image


def _preprocess(image: "Image.Image") -> "Image.Image":
    """Convert to greyscale, sharpen, and binarise (used for full-page OCR)."""
    image = image.convert("L")
    image = image.filter(ImageFilter.SHARPEN)
    image = ImageOps.autocontrast(image)
    image = image.point(lambda x: 0 if x < 140 else 255, "1")
    return image.convert("L")


def _ocr_full_page(image: "Image.Image") -> list[list[int]] | None:
    """
    Run Tesseract over the whole page image and try to parse the text as a grid.
    Works when the Sudoku is rendered as large, well-spaced text.
    """
    processed = _preprocess(image)
    text = pytesseract.image_to_string(processed, config="--psm 6 --oem 3")
    text = _normalise_ocr_text(text)
    return _try_text_parsing(text)


def _ocr_cell_by_cell(image: "Image.Image") -> list[list[int]] | None:
    """
    Locate the grid bounding box, divide into 81 cells, and OCR each one.
    Each cell is preprocessed individually for best digit recognition.
    """
    w, h = image.size
    detected = _detect_grid_box(image)
    grid_box = detected or (0, 0, w, h)
    print(f"  [parser] Image size: {w}x{h}, grid box: {grid_box} ({'detected' if detected else 'full page fallback'})")
    x0, y0, x1, y1 = grid_box
    gw, gh = x1 - x0, y1 - y0

    cell_w = gw / 9
    cell_h = gh / 9
    print(f"  [parser] Cell size: {cell_w:.0f}x{cell_h:.0f} px")
    if cell_w < 20 or cell_h < 20:
        print("  [parser] Cells too small — aborting cell-by-cell OCR")
        return None

    # Inset fraction — enough to clear grid lines but not clip digits
    inset_x = max(3, int(cell_w * 0.15))
    inset_y = max(3, int(cell_h * 0.15))
    # Target cell size to feed Tesseract (enlarge small cells)
    target_px = 80

    result = []
    for row in range(9):
        grid_row = []
        for col in range(9):
            cx0 = int(x0 + col * cell_w) + inset_x
            cy0 = int(y0 + row * cell_h) + inset_y
            cx1 = int(x0 + (col + 1) * cell_w) - inset_x
            cy1 = int(y0 + (row + 1) * cell_h) - inset_y

            cell_img = image.crop((cx0, cy0, cx1, cy1))

            # Upscale if cell is small
            cw, ch = cell_img.size
            if cw < target_px or ch < target_px:
                scale = max(target_px // max(cw, 1), target_px // max(ch, 1), 1)
                cell_img = cell_img.resize((cw * scale, ch * scale), Image.LANCZOS)

            cell_img = _preprocess_cell(cell_img)

            # Poll multiple PSM modes and take majority vote
            digit = _read_cell_digit(cell_img)
            grid_row.append(digit)
        result.append(grid_row)

    given = sum(1 for r in result for v in r if v != 0)
    print(f"  [parser] OCR cell-by-cell: found {given} filled cells")
    if given == 0:
        return None

    return result


def _detect_grid_box(image: "Image.Image") -> tuple[int, int, int, int] | None:
    """
    Heuristic: find the bounding box of the largest roughly-square dark
    connected region, which is typically the Sudoku grid border.

    Uses a simple row/column projection to find the densest ink region.
    Returns (x0, y0, x1, y1) or None if detection is inconclusive.
    """
    try:
        import numpy as np
    except ImportError:
        return None

    grey = image.convert("L")
    arr = np.array(grey)
    binary = (arr < 128).astype(np.uint8)  # 1 where dark

    row_density = binary.mean(axis=1)
    col_density = binary.mean(axis=0)

    # Find contiguous bands with above-average ink density
    row_thresh = row_density.mean() * 0.3
    col_thresh = col_density.mean() * 0.3

    row_mask = row_density > row_thresh
    col_mask = col_density > col_thresh

    rows_on = np.where(row_mask)[0]
    cols_on = np.where(col_mask)[0]

    if len(rows_on) < 50 or len(cols_on) < 50:
        return None

    y0, y1 = int(rows_on[0]), int(rows_on[-1])
    x0, x1 = int(cols_on[0]), int(cols_on[-1])

    # Require the detected region to be at least 100px in each dimension
    if (y1 - y0) < 100 or (x1 - x0) < 100:
        return None

    # Add a small margin
    margin = 5
    h, w = arr.shape
    return (
        max(0, x0 - margin),
        max(0, y0 - margin),
        min(w, x1 + margin),
        min(h, y1 + margin),
    )


def _read_cell_digit(cell_img: "Image.Image") -> int:
    """
    Run Tesseract with several PSM modes and return the digit by majority vote.
    Only counts a PSM result if it yields exactly one digit character.
    """
    from collections import Counter
    votes = []
    for psm in (6, 7, 8, 10):
        raw = pytesseract.image_to_string(
            cell_img,
            config=f"--psm {psm} --oem 3 -c tessedit_char_whitelist=0123456789",
        ).strip()
        raw = _normalise_ocr_text(raw)
        # Only accept results that yield a single unambiguous digit
        digits_found = [int(ch) for ch in raw if ch.isdigit() and int(ch) in range(1, 10)]
        if len(digits_found) == 1:
            votes.append(digits_found[0])
    if not votes:
        return 0
    return Counter(votes).most_common(1)[0][0]


def _normalise_ocr_text(text: str) -> str:
    """Fix common Tesseract misreads for Sudoku digits."""
    replacements = {
        "O": "0", "o": "0",
        "l": "1", "I": "1", "i": "1", "|": "1",
        "Z": "2", "z": "2",
        "S": "5", "s": "5",
        "G": "6", "g": "6",
        "B": "8",
        "q": "9", "g": "9",
    }
    result = []
    for ch in text:
        result.append(replacements.get(ch, ch))
    return "".join(result)


def _first_digit(text: str) -> int:
    """Return the first digit 1-9 found in text, or 0 if none."""
    for ch in text:
        if ch.isdigit():
            d = int(ch)
            if 1 <= d <= 9:
                return d
    return 0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate(grid: list[list[int]]) -> None:
    """
    Confirm the grid is 9x9, values 0-9, and no pre-filled digit appears
    twice in any row, column, or 3x3 box.
    """
    if len(grid) != 9:
        raise ValueError(f"Grid has {len(grid)} rows, expected 9.")
    for r, row in enumerate(grid):
        if len(row) != 9:
            raise ValueError(f"Row {r+1} has {len(row)} cells, expected 9.")
        for val in row:
            if not (0 <= val <= 9):
                raise ValueError(f"Invalid cell value {val} at row {r+1}.")

    for r in range(9):
        seen = [v for v in grid[r] if v != 0]
        if len(seen) != len(set(seen)):
            raise ValueError(f"Duplicate value in row {r+1}.")

    for c in range(9):
        seen = [grid[r][c] for r in range(9) if grid[r][c] != 0]
        if len(seen) != len(set(seen)):
            raise ValueError(f"Duplicate value in column {c+1}.")

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
