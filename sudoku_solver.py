#!/usr/bin/env python3
"""
sudoku_solver.py — CLI entry point for the PDF Sudoku Solver.

Usage:
    python3 sudoku_solver.py

The program will prompt for the path to a PDF containing a Sudoku puzzle,
solve it, and write a result PDF to the same directory with '_solution'
appended to the filename.
"""

import os
import sys

from pdf_parser import extract_grid
from solver import solve
from pdf_reporter import generate_report


def main() -> None:
    print("=" * 50)
    print("  Sudoku Solver — PDF Edition")
    print("=" * 50)
    print()

    # Prompt for input PDF
    pdf_path = input("Enter path to Sudoku PDF: ").strip()
    if not pdf_path:
        print("Error: No path provided.", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(pdf_path):
        print(f"Error: File not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    # Extract grid
    print("\nExtracting puzzle from PDF...")
    try:
        grid = extract_grid(pdf_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    given_count = sum(1 for r in grid for v in r if v != 0)
    print(f"Puzzle extracted successfully ({given_count} given digits).")
    print()
    _print_grid(grid)
    print()

    # Solve
    print("Solving...")
    try:
        solved, steps = solve(grid)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Solved in {len(steps)} steps.")
    print()
    _print_grid(solved)
    print()

    # Generate output PDF
    base, ext = os.path.splitext(pdf_path)
    output_path = base + "_solution.pdf"
    print(f"Generating report PDF: {output_path}")
    try:
        generate_report(output_path, grid, solved, steps)
    except Exception as exc:
        print(f"Error generating report: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\nDone! Solution written to: {output_path}")


def _print_grid(grid: list[list[int]]) -> None:
    """Pretty-print the grid to stdout."""
    for r, row in enumerate(grid):
        if r % 3 == 0 and r != 0:
            print("+-------+-------+-------+")
        cells = [str(v) if v != 0 else "." for v in row]
        print(
            "| " + " ".join(cells[0:3])
            + " | " + " ".join(cells[3:6])
            + " | " + " ".join(cells[6:9])
            + " |"
        )


if __name__ == "__main__":
    main()
