"""Fill holes inside enclosed objects."""
from __future__ import annotations

import random
from typing import Dict, Any, List

from ..utils import new_grid, random_color, place_rect_border, place_rect, copy_grid

Grid = List[List[int]]

CONCEPT = "holes_fill"
CHAPTER = "objectness_topology"
DESCRIPTION = "Identify enclosed holes in ring objects and fill them with a target color."


def _add_ring(grid: Grid, ring_color: int) -> None:
    h = len(grid)
    w = len(grid[0])
    ring_h = random.randint(4, max(4, h // 2))
    ring_w = random.randint(4, max(4, w // 2))
    top = random.randint(0, h - ring_h)
    left = random.randint(0, w - ring_w)
    place_rect_border(grid, top, left, ring_h, ring_w, ring_color)


def _fill_holes(grid: Grid, ring_color: int, fill_color: int) -> Grid:
    out = copy_grid(grid)
    h = len(grid)
    w = len(grid[0])
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            if grid[r][c] == 0:
                if grid[r - 1][c] == ring_color and grid[r + 1][c] == ring_color:
                    if grid[r][c - 1] == ring_color and grid[r][c + 1] == ring_color:
                        out[r][c] = fill_color
    return out


def _generate_pair() -> Dict[str, Grid]:
    h = random.randint(8, 14)
    w = random.randint(8, 14)
    grid = new_grid(h, w, 0)
    ring_color = random_color()
    fill_color = random_color(exclude=(0, ring_color))

    for _ in range(random.randint(1, 3)):
        _add_ring(grid, ring_color)

    for _ in range(random.randint(1, 2)):
        rh = random.randint(2, 3)
        rw = random.randint(2, 3)
        top = random.randint(0, h - rh)
        left = random.randint(0, w - rw)
        place_rect(grid, top, left, rh, rw, random_color(exclude=(0, ring_color, fill_color)))

    out = _fill_holes(grid, ring_color, fill_color)
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
