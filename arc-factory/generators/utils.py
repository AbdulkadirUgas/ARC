"""Shared grid utilities for generators."""
from __future__ import annotations

import random
from typing import List, Tuple

Grid = List[List[int]]


def new_grid(h: int, w: int, color: int = 0) -> Grid:
    return [[color for _ in range(w)] for _ in range(h)]


def random_color(exclude: Tuple[int, ...] = (0,)) -> int:
    choices = [c for c in range(10) if c not in exclude]
    return random.choice(choices)


def place_rect(grid: Grid, top: int, left: int, height: int, width: int, color: int) -> None:
    for r in range(top, top + height):
        for c in range(left, left + width):
            grid[r][c] = color


def place_rect_border(grid: Grid, top: int, left: int, height: int, width: int, color: int) -> None:
    for r in range(top, top + height):
        for c in range(left, left + width):
            if r in (top, top + height - 1) or c in (left, left + width - 1):
                grid[r][c] = color


def copy_grid(grid: Grid) -> Grid:
    return [row[:] for row in grid]


def reflect_y(grid: Grid) -> Grid:
    return [row[::-1] for row in grid]


def rotate90(grid: Grid) -> Grid:
    return [list(row) for row in zip(*grid[::-1])]
