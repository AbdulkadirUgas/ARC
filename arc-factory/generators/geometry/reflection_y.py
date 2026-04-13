"""Reflect pattern across Y-axis."""
from __future__ import annotations

import random
from typing import Dict, Any, List

from ..utils import new_grid, random_color, place_rect, reflect_y, copy_grid

Grid = List[List[int]]

CONCEPT = "reflection_y"
CHAPTER = "geometry_symmetry"
DESCRIPTION = "Reflect the input pattern across the vertical (Y) axis."


def _draw_pattern(grid: Grid) -> None:
    h = len(grid)
    w = len(grid[0])
    for _ in range(random.randint(3, 6)):
        rh = random.randint(1, max(1, h // 3))
        rw = random.randint(1, max(1, w // 3))
        top = random.randint(0, h - rh)
        left = random.randint(0, w // 2 - rw)
        color = random_color()
        place_rect(grid, top, left, rh, rw, color)


def _generate_pair() -> Dict[str, Grid]:
    h = random.randint(8, 16)
    w = random.randint(8, 16)
    grid = new_grid(h, w, 0)
    _draw_pattern(grid)
    out = reflect_y(copy_grid(grid))
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
