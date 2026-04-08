"""
pdf_reporter.py — Generate a PDF report for the solved Sudoku puzzle.

The report contains three sections:
  1. Original Puzzle  — the grid as extracted from the input PDF
  2. Solution         — the fully completed grid (solved cells in blue)
  3. Solving Steps    — numbered log of every action the solver took
"""

from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
)
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from solver import Step


# Colour palette
_GIVEN_COLOR = colors.black
_SOLVED_COLOR = colors.HexColor("#1a56db")   # blue for solver-placed digits
_GRID_LINE_THIN = 0.5
_GRID_LINE_THICK = 2.0
_CELL_SIZE = 36   # points


def generate_report(
    output_path: str,
    original_grid: list[list[int]],
    solved_grid: list[list[int]],
    steps: list[Step],
) -> None:
    """
    Write a three-section PDF to output_path.

    Args:
        output_path:    Destination file path for the report PDF.
        original_grid:  9x9 grid as extracted from the input (0 = empty).
        solved_grid:    9x9 fully-solved grid.
        steps:          Ordered list of solving steps from solver.solve().
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )

    styles = getSampleStyleSheet()
    story = _build_story(original_grid, solved_grid, steps, styles)
    doc.build(story)


# ---------------------------------------------------------------------------
# Story builder
# ---------------------------------------------------------------------------

def _build_story(
    original_grid: list[list[int]],
    solved_grid: list[list[int]],
    steps: list[Step],
    styles,
) -> list:
    title_style = ParagraphStyle(
        "SudokuTitle",
        parent=styles["Title"],
        fontSize=22,
        spaceAfter=6,
        alignment=TA_CENTER,
    )
    h2_style = ParagraphStyle(
        "SudokuH2",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=18,
        spaceAfter=8,
        alignment=TA_LEFT,
    )
    note_style = ParagraphStyle(
        "SudokuNote",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.grey,
        spaceAfter=10,
        alignment=TA_CENTER,
    )
    step_style = ParagraphStyle(
        "SudokuStep",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        spaceAfter=2,
    )
    backtrack_style = ParagraphStyle(
        "SudokuBacktrack",
        parent=step_style,
        textColor=colors.HexColor("#b91c1c"),  # red for backtracks
    )

    story = []

    # ---- Title ----
    story.append(Paragraph("Sudoku Solver Report", title_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 12))

    # ---- Section 1: Original Puzzle ----
    story.append(Paragraph("1. Original Puzzle", h2_style))
    story.append(
        Paragraph("Given numbers are shown in black. Empty cells are shown as ·", note_style)
    )
    story.append(_build_grid_table(original_grid, original_grid=None, show_given_as_empty=False))
    story.append(Spacer(1, 20))

    # ---- Section 2: Solution ----
    story.append(Paragraph("2. Solution", h2_style))
    story.append(
        Paragraph(
            "Given numbers in black · Solver-placed numbers in <font color=\"#1a56db\">blue</font>",
            note_style,
        )
    )
    story.append(_build_grid_table(solved_grid, original_grid=original_grid))
    story.append(Spacer(1, 20))

    # ---- Section 3: Solving Steps ----
    story.append(Paragraph("3. Solving Steps", h2_style))

    naked_count = sum(1 for s in steps if s.reason == "Naked single")
    trial_count = sum(1 for s in steps if s.reason == "Trial (backtracking)")
    bt_count = sum(1 for s in steps if s.reason == "Backtrack")
    summary = (
        f"Total steps: {len(steps)} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Naked singles: {naked_count} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Trials: {trial_count} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Backtracks: {bt_count}"
    )
    story.append(Paragraph(summary, note_style))

    if not steps:
        story.append(Paragraph("(Puzzle was already complete.)", step_style))
    else:
        for step in steps:
            is_backtrack = step.reason == "Backtrack"
            story.append(Paragraph(str(step), backtrack_style if is_backtrack else step_style))

    return story


# ---------------------------------------------------------------------------
# Grid table builder
# ---------------------------------------------------------------------------

def _build_grid_table(
    grid: list[list[int]],
    original_grid: list[list[int]] | None,
    show_given_as_empty: bool = False,
) -> Table:
    """
    Build a reportlab Table representing the Sudoku grid.

    Args:
        grid:             Values to display (0 = empty).
        original_grid:    If provided, cells that were 0 in original_grid are
                          styled as solver-placed (blue). If None, all non-zero
                          cells are styled as givens (black bold).
        show_given_as_empty: If True, non-zero cells are shown as-is; empty as ·
    """
    cell_font_given = "Helvetica-Bold"
    cell_font_solved = "Helvetica"
    cell_size = _CELL_SIZE

    # Build 2D list of Paragraph objects
    data = []
    for r in range(9):
        row_cells = []
        for c in range(9):
            val = grid[r][c]
            if val == 0:
                text = "\u00b7"  # middle dot
                para = Paragraph(
                    f'<font name="Helvetica" size="16" color="#cccccc">{text}</font>',
                    _centered_style(),
                )
            else:
                is_given = (original_grid is None) or (original_grid[r][c] != 0)
                if is_given:
                    para = Paragraph(
                        f'<font name="{cell_font_given}" size="14" color="#000000">{val}</font>',
                        _centered_style(),
                    )
                else:
                    para = Paragraph(
                        f'<font name="{cell_font_solved}" size="14" color="#1a56db">{val}</font>',
                        _centered_style(),
                    )
            row_cells.append(para)
        data.append(row_cells)

    col_widths = [cell_size] * 9
    row_heights = [cell_size] * 9

    table = Table(data, colWidths=col_widths, rowHeights=row_heights)
    table.setStyle(_grid_style())
    return table


def _centered_style() -> ParagraphStyle:
    return ParagraphStyle(
        "GridCell",
        alignment=TA_CENTER,
        leading=_CELL_SIZE,
        fontSize=14,
    )


def _grid_style() -> TableStyle:
    """Build TableStyle with thin inner lines and thick 3x3 box borders."""
    cmds = [
        # Background
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        # Alignment
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # Outer border
        ("BOX", (0, 0), (-1, -1), _GRID_LINE_THICK, colors.black),
        # All inner lines (thin)
        ("INNERGRID", (0, 0), (-1, -1), _GRID_LINE_THIN, colors.HexColor("#999999")),
        # Padding
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]

    # Thick lines between 3x3 boxes (vertical)
    for col in (3, 6):
        cmds.append(("LINEAFTER", (col - 1, 0), (col - 1, 8), _GRID_LINE_THICK, colors.black))

    # Thick lines between 3x3 boxes (horizontal)
    for row in (3, 6):
        cmds.append(("LINEBELOW", (0, row - 1), (8, row - 1), _GRID_LINE_THICK, colors.black))

    return TableStyle(cmds)
