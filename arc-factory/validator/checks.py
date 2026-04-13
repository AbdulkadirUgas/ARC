"""Validation checks for ARC-like tasks."""
from __future__ import annotations

from typing import Dict, List, Tuple, Any

Grid = List[List[int]]
Pair = Dict[str, Grid]
Task = Dict[str, Any]


def _is_solid_color(grid: Grid) -> bool:
    if not grid or not grid[0]:
        return True
    color = grid[0][0]
    return all(cell == color for row in grid for cell in row)


def _grids_equal(a: Grid, b: Grid) -> bool:
    return a == b


def _rotate90(grid: Grid) -> Grid:
    return [list(row) for row in zip(*grid[::-1])]


def _flip_h(grid: Grid) -> Grid:
    return [row[::-1] for row in grid]


def _flip_v(grid: Grid) -> Grid:
    return grid[::-1]


def _attempt_baseline_solve(inp: Grid) -> List[Grid]:
    variants = [
        inp,
        _flip_h(inp),
        _flip_v(inp),
        _rotate90(inp),
        _rotate90(_rotate90(inp)),
        _rotate90(_rotate90(_rotate90(inp))),
    ]
    return variants


def _baseline_solves_pair(inp: Grid, out: Grid) -> bool:
    for candidate in _attempt_baseline_solve(inp):
        if _grids_equal(candidate, out):
            return True
    return False


def _check_non_trivial(task: Task) -> bool:
    allow_identity = task.get("meta", {}).get("allow_identity", False)
    if allow_identity:
        return True
    for pair in task.get("train", []) + task.get("test", []):
        if _grids_equal(pair["input"], pair["output"]):
            return False
    return True


def _check_not_solid(task: Task) -> bool:
    allow_solid = task.get("meta", {}).get("allow_solid_output", False)
    if allow_solid:
        return True
    for pair in task.get("train", []) + task.get("test", []):
        if _is_solid_color(pair["output"]):
            return False
    return True


def _check_baseline_not_trivial(task: Task) -> bool:
    """Reject tasks solvable by trivial transforms on all pairs."""
    all_pairs = task.get("train", []) + task.get("test", [])
    if not all_pairs:
        return False
    solved_all = all(_baseline_solves_pair(p["input"], p["output"]) for p in all_pairs)
    return not solved_all


def validate_task(task: Task) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    if not _check_non_trivial(task):
        errors.append("non_triviality_failed")

    if not _check_not_solid(task):
        errors.append("solid_output_failed")

    if not _check_baseline_not_trivial(task):
        errors.append("baseline_solver_solved")

    return len(errors) == 0, errors
