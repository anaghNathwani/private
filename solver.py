from __future__ import annotations

"""
solver.py — Solve a 9x9 Sudoku puzzle with constraint propagation + backtracking.

Algorithm:
  1. Naked-singles propagation: repeatedly scan for empty cells with only one
     candidate and fill them in.
  2. Backtracking with MRV (Minimum Remaining Values): when propagation stalls,
     pick the unfilled cell with the fewest candidates and try each in turn,
     recursing and backtracking on failure.

Every placement is recorded as a Step so the caller can present a step-by-step
explanation in the output PDF.
"""

import copy
from dataclasses import dataclass, field


@dataclass
class Step:
    step_num: int
    row: int        # 1-indexed
    col: int        # 1-indexed
    value: int
    reason: str     # e.g. "Naked single", "Trial (backtracking)", "Backtrack"

    def __str__(self) -> str:
        if self.reason == "Backtrack":
            return (
                f"Step {self.step_num}: Row {self.row}, Col {self.col} "
                f"— backtrack (value {self.value} led to contradiction)"
            )
        return (
            f"Step {self.step_num}: Row {self.row}, Col {self.col} "
            f"\u2192 place {self.value} ({self.reason})"
        )


def solve(grid: list[list[int]]) -> tuple[list[list[int]], list[Step]]:
    """
    Solve the given 9x9 Sudoku grid.

    Args:
        grid: 9x9 list of ints; 0 represents an empty cell.

    Returns:
        (solved_grid, steps) where solved_grid is the completed puzzle and
        steps is the ordered list of actions taken.

    Raises:
        ValueError: if the puzzle has no solution.
    """
    working = copy.deepcopy(grid)
    steps: list[Step] = []
    counter = _Counter()

    # Phase 1: naked-singles propagation
    _apply_naked_singles(working, steps, counter)

    # Phase 2: backtracking (if still unsolved)
    if _has_empty(working):
        success = _backtrack(working, steps, counter)
        if not success:
            raise ValueError("Puzzle has no solution.")

    # Renumber sequentially so the final list has gapless step numbers
    for i, step in enumerate(steps, start=1):
        step.step_num = i

    return working, steps


# ---------------------------------------------------------------------------
# Internal state helpers
# ---------------------------------------------------------------------------

class _Counter:
    """Mutable step counter shared across recursive calls."""
    def __init__(self) -> None:
        self.n = 0

    def next(self) -> int:
        self.n += 1
        return self.n


def _candidates(grid: list[list[int]], r: int, c: int) -> set[int]:
    """Return the set of valid digits for cell (r, c)."""
    used: set[int] = set()
    # Row
    used.update(grid[r])
    # Column
    used.update(grid[i][c] for i in range(9))
    # 3x3 box
    br, bc = (r // 3) * 3, (c // 3) * 3
    for dr in range(3):
        for dc in range(3):
            used.add(grid[br + dr][bc + dc])
    used.discard(0)
    return set(range(1, 10)) - used


def _has_empty(grid: list[list[int]]) -> bool:
    return any(grid[r][c] == 0 for r in range(9) for c in range(9))


def _empty_cells(grid: list[list[int]]) -> list[tuple[int, int]]:
    return [(r, c) for r in range(9) for c in range(9) if grid[r][c] == 0]


# ---------------------------------------------------------------------------
# Phase 1: Naked-singles propagation
# ---------------------------------------------------------------------------

def _apply_naked_singles(
    grid: list[list[int]],
    steps: list[Step],
    counter: _Counter,
) -> None:
    """
    Repeatedly scan the grid and fill any cell that has exactly one candidate.
    Continues until no more naked singles are found.
    """
    changed = True
    while changed:
        changed = False
        for r in range(9):
            for c in range(9):
                if grid[r][c] != 0:
                    continue
                cands = _candidates(grid, r, c)
                if len(cands) == 0:
                    # Contradiction — caller (backtracker) will handle this
                    return
                if len(cands) == 1:
                    val = next(iter(cands))
                    grid[r][c] = val
                    steps.append(Step(counter.next(), r + 1, c + 1, val, "Naked single"))
                    changed = True


# ---------------------------------------------------------------------------
# Phase 2: Backtracking with MRV
# ---------------------------------------------------------------------------

def _backtrack(
    grid: list[list[int]],
    steps: list[Step],
    counter: _Counter,
) -> bool:
    """
    Recursive backtracking solver. Returns True when solved, False on failure.
    Uses Minimum Remaining Values (MRV) heuristic to choose the next cell.
    """
    # Find the unfilled cell with the fewest candidates (MRV)
    best_r, best_c, best_cands = -1, -1, None
    for r in range(9):
        for c in range(9):
            if grid[r][c] != 0:
                continue
            cands = _candidates(grid, r, c)
            if len(cands) == 0:
                return False  # Dead end
            if best_cands is None or len(cands) < len(best_cands):
                best_r, best_c, best_cands = r, c, cands

    if best_r == -1:
        return True  # All cells filled — solved!

    for val in sorted(best_cands):
        grid[best_r][best_c] = val
        trial_step_num = counter.next()
        steps.append(Step(trial_step_num, best_r + 1, best_c + 1, val, "Trial (backtracking)"))

        # Apply naked-singles on top of this guess
        saved = copy.deepcopy(grid)
        saved_steps_len = len(steps)
        _apply_naked_singles(grid, steps, counter)

        if _has_contradiction(grid):
            # Restore and record backtrack
            _restore(grid, saved)
            _trim_steps(steps, saved_steps_len)
            steps.append(Step(counter.next(), best_r + 1, best_c + 1, val, "Backtrack"))
            continue

        if _backtrack(grid, steps, counter):
            return True

        # Backtrack
        _restore(grid, saved)
        _trim_steps(steps, saved_steps_len)
        steps.append(Step(counter.next(), best_r + 1, best_c + 1, val, "Backtrack"))

    return False


def _has_contradiction(grid: list[list[int]]) -> bool:
    """Return True if any empty cell has zero candidates."""
    return any(
        grid[r][c] == 0 and len(_candidates(grid, r, c)) == 0
        for r in range(9)
        for c in range(9)
    )


def _restore(grid: list[list[int]], saved: list[list[int]]) -> None:
    for r in range(9):
        for c in range(9):
            grid[r][c] = saved[r][c]


def _trim_steps(steps: list[Step], length: int) -> None:
    """Remove steps added after the checkpoint (they belong to the failed branch)."""
    del steps[length:]
