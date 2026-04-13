"""Copy top-left quadrant pattern to other quadrants."""
from __future__ import annotations

import random
from typing import Dict, Any, List

from ..utils import new_grid, random_color, place_rect

Grid = List[List[int]]

CONCEPT = "quadrant_copy"
CHAPTER = "abstract_pattern_matching"
DESCRIPTION = "Apply the top-left quadrant pattern to all other quadrants."


def _generate_pair() -> Dict[str, Grid]:
    size = random.choice([6, 8, 10])
    half = size // 2
    grid = new_grid(size, size, 0)

    for _ in range(random.randint(2, 4)):
        rh = random.randint(1, max(1, half // 2))
        rw = random.randint(1, max(1, half // 2))
        top = random.randint(0, half - rh)
        left = random.randint(0, half - rw)
        color = random_color()
        place_rect(grid, top, left, rh, rw, color)

    out = new_grid(size, size, 0)
    for r in range(half):
        for c in range(half):
            val = grid[r][c]
            out[r][c] = val
            out[r][c + half] = val
            out[r + half][c] = val
            out[r + half][c + half] = val

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
