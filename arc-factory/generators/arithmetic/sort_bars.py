"""Sort vertical bars by height."""
from __future__ import annotations

import random
from typing import Dict, Any, List, Tuple

from ..utils import new_grid, random_color

Grid = List[List[int]]

CONCEPT = "sort_bars"
CHAPTER = "arithmetic_counting"
DESCRIPTION = "Sort vertical bars from shortest to tallest, preserving their colors."


def _generate_bars(h: int, w: int) -> Tuple[Grid, List[Tuple[int, int]]]:
    grid = new_grid(h, w, 0)
    num_bars = random.randint(3, min(6, w))
    positions = random.sample(range(w), num_bars)
    bars: List[Tuple[int, int]] = []
    for c in positions:
        height = random.randint(2, h - 1)
        color = random_color()
        for r in range(h - 1, h - 1 - height, -1):
            grid[r][c] = color
        bars.append((height, color))
    return grid, bars


def _render_sorted(h: int, w: int, bars: List[Tuple[int, int]]) -> Grid:
    out = new_grid(h, w, 0)
    sorted_bars = sorted(bars, key=lambda x: x[0])
    for idx, (height, color) in enumerate(sorted_bars):
        c = idx
        for r in range(h - 1, h - 1 - height, -1):
            out[r][c] = color
    return out


def _generate_pair() -> Dict[str, Grid]:
    h = random.randint(8, 14)
    w = random.randint(6, 10)
    grid, bars = _generate_bars(h, w)
    out = _render_sorted(h, w, bars)
    return {"input": grid, "output": out}


def generate(seed: int | None = None) -> Dict[str, Any]:
    if seed is not None:
        random.seed(seed)

    train = [_generate_pair() for _ in range(random.randint(3, 5))]
    test = [_generate_pair()]

    return {
        "train": train,
        "test": test,
        "meta": {"concept": CONCEPT, "chapter": CHAPTER, "description": DESCRIPTION},
    }
