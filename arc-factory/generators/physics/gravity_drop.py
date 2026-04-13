"""Drop red pixels until they hit a green blocker or bottom edge."""
from __future__ import annotations

import random
from typing import Dict, Any, List

from ..utils import new_grid, random_color, copy_grid

Grid = List[List[int]]

CONCEPT = "gravity_drop"
CHAPTER = "physics_causality"
DESCRIPTION = "Move all red pixels down until they hit a green pixel or the grid edge."


def _apply_gravity(grid: Grid, particle_color: int, blocker_color: int) -> Grid:
    h = len(grid)
    w = len(grid[0])
    out = new_grid(h, w, 0)

    for r in range(h):
        for c in range(w):
            if grid[r][c] == blocker_color:
                out[r][c] = blocker_color

    for c in range(w):
        blockers = [-1] + [r for r in range(h) if grid[r][c] == blocker_color] + [h]
        for i in range(len(blockers) - 1):
            start = blockers[i]
            end = blockers[i + 1]
            count = sum(1 for r in range(start + 1, end) if grid[r][c] == particle_color)
            for r in range(end - 1, end - 1 - count, -1):
                out[r][c] = particle_color
    return out


def _generate_pair() -> Dict[str, Grid]:
    h = random.randint(8, 16)
    w = random.randint(6, 12)
    grid = new_grid(h, w, 0)
    particle_color = 2
    blocker_color = 3

    for _ in range(random.randint(4, 8)):
        r = random.randint(0, h - 1)
        c = random.randint(0, w - 1)
        grid[r][c] = blocker_color

    for _ in range(random.randint(6, 14)):
        r = random.randint(0, h - 1)
        c = random.randint(0, w - 1)
        if grid[r][c] == 0:
            grid[r][c] = particle_color

    out = _apply_gravity(grid, particle_color, blocker_color)
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
