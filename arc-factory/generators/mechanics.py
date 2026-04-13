"""Unified generator covering multiple ARC mechanics."""
from __future__ import annotations

import random
from collections import deque
from typing import Any, Dict, List, Tuple, Callable

from .utils import (
    new_grid,
    random_color,
    place_rect,
    place_rect_border,
    copy_grid,
    reflect_y,
    rotate90,
)

Grid = List[List[int]]
Task = Dict[str, Any]


def _reflect_x(grid: Grid) -> Grid:
    return grid[::-1]


def _rotate180(grid: Grid) -> Grid:
    return rotate90(rotate90(grid))


def _neighbors(h: int, w: int, r: int, c: int) -> List[Tuple[int, int]]:
    out = []
    if r > 0:
        out.append((r - 1, c))
    if r + 1 < h:
        out.append((r + 1, c))
    if c > 0:
        out.append((r, c - 1))
    if c + 1 < w:
        out.append((r, c + 1))
    return out


def _components(grid: Grid, target_color: int | None = None) -> List[List[Tuple[int, int]]]:
    h, w = len(grid), len(grid[0])
    seen = [[False] * w for _ in range(h)]
    comps = []
    for r in range(h):
        for c in range(w):
            if seen[r][c]:
                continue
            if target_color is None:
                if grid[r][c] == 0:
                    continue
            else:
                if grid[r][c] != target_color:
                    continue
            color = grid[r][c]
            q = deque([(r, c)])
            seen[r][c] = True
            comp = []
            while q:
                cr, cc = q.popleft()
                comp.append((cr, cc))
                for nr, nc in _neighbors(h, w, cr, cc):
                    if seen[nr][nc]:
                        continue
                    if target_color is None:
                        if grid[nr][nc] != color:
                            continue
                    else:
                        if grid[nr][nc] != target_color:
                            continue
                    seen[nr][nc] = True
                    q.append((nr, nc))
            comps.append(comp)
    return comps


def _bbox(cells: List[Tuple[int, int]]) -> Tuple[int, int, int, int]:
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), min(cs), max(rs), max(cs)


def _draw_line(grid: Grid, a: Tuple[int, int], b: Tuple[int, int], color: int) -> None:
    r1, c1 = a
    r2, c2 = b
    r, c = r1, c1
    grid[r][c] = color
    while c != c2:
        c += 1 if c2 > c else -1
        grid[r][c] = color
    while r != r2:
        r += 1 if r2 > r else -1
        grid[r][c] = color


def _bfs_path(grid: Grid, start: Tuple[int, int], goal: Tuple[int, int], blocked: int) -> List[Tuple[int, int]]:
    h, w = len(grid), len(grid[0])
    q = deque([start])
    prev = {start: None}
    while q:
        r, c = q.popleft()
        if (r, c) == goal:
            break
        for nr, nc in _neighbors(h, w, r, c):
            if (nr, nc) in prev:
                continue
            if grid[nr][nc] == blocked:
                continue
            prev[(nr, nc)] = (r, c)
            q.append((nr, nc))
    if goal not in prev:
        return []
    path = []
    cur = goal
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path


def _apply_gravity(grid: Grid, direction: str) -> Grid:
    h, w = len(grid), len(grid[0])
    out = new_grid(h, w, 0)
    if direction in ("down", "up"):
        rng = range(h) if direction == "up" else range(h - 1, -1, -1)
        for c in range(w):
            stack = [grid[r][c] for r in rng if grid[r][c] != 0]
            for i, r in enumerate(rng):
                if i < len(stack):
                    out[r][c] = stack[i]
    else:
        rng = range(w) if direction == "left" else range(w - 1, -1, -1)
        for r in range(h):
            stack = [grid[r][c] for c in rng if grid[r][c] != 0]
            for i, c in enumerate(rng):
                if i < len(stack):
                    out[r][c] = stack[i]
    return out


def _clone_pair(pair: Dict[str, Grid]) -> Dict[str, Grid]:
    return {"input": copy_grid(pair["input"]), "output": copy_grid(pair["output"])}


def _base_task(meta: Dict[str, Any], pairs: List[Dict[str, Grid]]) -> Task:
    if len(pairs) == 1:
        pair = pairs[0]
        train = [_clone_pair(pair) for _ in range(3)]
        test = [_clone_pair(pair)]
        return {"train": train, "test": test, "meta": meta}
    return {"train": pairs[:-1], "test": pairs[-1:], "meta": meta}


# ---------------- Category A ----------------

def _reflection_x() -> Task:
    h, w = random.randint(8, 14), random.randint(8, 14)
    grid = new_grid(h, w, 0)
    for _ in range(random.randint(3, 6)):
        place_rect(grid, random.randint(0, h - 2), random.randint(0, w - 2), 1, 2, random_color())
    out = _reflect_x(copy_grid(grid))
    return _base_task({"concept": "reflection_x"}, [{"input": grid, "output": out}])


def _reflection_y() -> Task:
    h, w = random.randint(8, 14), random.randint(8, 14)
    grid = new_grid(h, w, 0)
    for _ in range(random.randint(3, 6)):
        place_rect(grid, random.randint(0, h - 2), random.randint(0, w - 2), 2, 1, random_color())
    out = reflect_y(copy_grid(grid))
    return _base_task({"concept": "reflection_y"}, [{"input": grid, "output": out}])


def _rotation_90() -> Task:
    h, w = random.randint(6, 10), random.randint(6, 10)
    grid = new_grid(h, w, 0)
    for _ in range(random.randint(3, 5)):
        place_rect(grid, random.randint(0, h - 2), random.randint(0, w - 2), 2, 2, random_color())
    out = rotate90(copy_grid(grid))
    return _base_task({"concept": "rotation_90"}, [{"input": grid, "output": out}])


def _rotation_180() -> Task:
    h, w = random.randint(6, 10), random.randint(6, 10)
    grid = new_grid(h, w, 0)
    for _ in range(random.randint(3, 5)):
        rh, rw = 1, 3
        top = random.randint(0, h - rh)
        left = random.randint(0, w - rw)
        place_rect(grid, top, left, rh, rw, random_color())
    out = _rotate180(copy_grid(grid))
    return _base_task({"concept": "rotation_180"}, [{"input": grid, "output": out}])


def _tiling() -> Task:
    tile = new_grid(3, 3, 0)
    place_rect(tile, 1, 1, 1, 1, random_color())
    out = new_grid(9, 9, 0)
    for tr in range(0, 9, 3):
        for tc in range(0, 9, 3):
            for r in range(3):
                for c in range(3):
                    out[tr + r][tc + c] = tile[r][c]
    return _base_task({"concept": "tiling"}, [{"input": tile, "output": out}])


def _crop_to_content() -> Task:
    h, w = random.randint(8, 12), random.randint(8, 12)
    grid = new_grid(h, w, 0)
    color = random_color()
    rh, rw = random.randint(2, 4), random.randint(2, 4)
    top, left = random.randint(1, h - rh - 1), random.randint(1, w - rw - 1)
    place_rect(grid, top, left, rh, rw, color)
    out = [row[left : left + rw] for row in grid[top : top + rh]]
    return _base_task({"concept": "crop_to_content"}, [{"input": grid, "output": out}])


def _upscale_2x() -> Task:
    h, w = random.randint(4, 6), random.randint(4, 6)
    grid = new_grid(h, w, 0)
    for _ in range(random.randint(2, 4)):
        grid[random.randint(0, h - 1)][random.randint(0, w - 1)] = random_color()
    out = new_grid(h * 2, w * 2, 0)
    for r in range(h):
        for c in range(w):
            val = grid[r][c]
            out[2 * r][2 * c] = val
            out[2 * r + 1][2 * c] = val
            out[2 * r][2 * c + 1] = val
            out[2 * r + 1][2 * c + 1] = val
    return _base_task({"concept": "upscale_2x"}, [{"input": grid, "output": out}])


def _downscale_2x() -> Task:
    h, w = random.randint(8, 10), random.randint(8, 10)
    grid = new_grid(h, w, 0)
    for r in range(0, h, 2):
        for c in range(0, w, 2):
            grid[r][c] = random_color()
    out_h = h // 2
    out_w = w // 2
    out = new_grid(out_h, out_w, 0)
    for r in range(0, out_h * 2, 2):
        for c in range(0, out_w * 2, 2):
            out[r // 2][c // 2] = grid[r][c]
    return _base_task({"concept": "downscale_2x"}, [{"input": grid, "output": out}])


def _symmetry_completion() -> Task:
    size = random.choice([8, 10, 12])
    half = size // 2
    grid = new_grid(size, size, 0)
    for _ in range(random.randint(3, 5)):
        r = random.randint(0, size - 1)
        c = random.randint(0, half - 1)
        grid[r][c] = random_color()
    out = copy_grid(grid)
    for r in range(size):
        for c in range(half):
            out[r][size - 1 - c] = out[r][c]
    return _base_task({"concept": "symmetry_completion"}, [{"input": grid, "output": out}])


def _axis_alignment() -> Task:
    h, w = random.randint(8, 12), random.randint(8, 12)
    grid = new_grid(h, w, 0)
    color = random_color()
    rh, rw = random.randint(2, 3), random.randint(2, 3)
    place_rect(grid, random.randint(2, h - rh - 1), random.randint(2, w - rw - 1), rh, rw, color)
    out = new_grid(h, w, 0)
    place_rect(out, 0, 0, rh, rw, color)
    return _base_task({"concept": "axis_alignment"}, [{"input": grid, "output": out}])


# ---------------- Category B ----------------

def _gravity_drop(direction: str) -> Task:
    h, w = random.randint(8, 12), random.randint(6, 10)
    grid = new_grid(h, w, 0)
    for _ in range(random.randint(6, 12)):
        grid[random.randint(0, h - 1)][random.randint(0, w - 1)] = random_color()
    out = _apply_gravity(grid, direction)
    return _base_task({"concept": f"gravity_{direction}"}, [{"input": grid, "output": out}])


def _object_collision() -> Task:
    h, w = random.randint(8, 12), random.randint(8, 12)
    grid = new_grid(h, w, 0)
    color_a = random_color()
    color_b = random_color(exclude=(0, color_a))
    place_rect(grid, 2, 1, 2, 2, color_a)
    place_rect(grid, 2, w - 3, 2, 2, color_b)
    out = copy_grid(grid)
    for r in range(2, 4):
        out[r][1] = 0
        out[r][2] = 0
        out[r][w - 4] = color_a
        out[r][w - 5] = color_a
    return _base_task({"concept": "object_collision"}, [{"input": grid, "output": out}])


def _sliding_puzzle() -> Task:
    h, w = 8, 8
    grid = new_grid(h, w, 0)
    colors = [random_color(), random_color(), random_color()]
    for idx, col in enumerate(colors):
        place_rect(grid, 1 + idx * 2, 1, 1, 2, col)
        place_rect(grid, 1 + idx * 2, w - 3, 1, 2, col)
    out = new_grid(h, w, 0)
    for idx, col in enumerate(colors):
        place_rect(out, 1 + idx * 2, w - 3, 1, 2, col)
    return _base_task({"concept": "sliding_puzzle"}, [{"input": grid, "output": out}])


def _magnetism() -> Task:
    h, w = 10, 10
    grid = new_grid(h, w, 0)
    attract = random_color()
    mover = random_color(exclude=(0, attract))
    grid[5][5] = attract
    grid[1][1] = mover
    out = copy_grid(grid)
    out[1][1] = 0
    out[4][5] = mover
    return _base_task({"concept": "magnetism"}, [{"input": grid, "output": out}])


def _repulsion() -> Task:
    h, w = 10, 10
    grid = new_grid(h, w, 0)
    repel = random_color()
    mover = random_color(exclude=(0, repel))
    grid[5][5] = repel
    grid[5][6] = mover
    out = copy_grid(grid)
    out[5][6] = 0
    out[5][8] = mover
    return _base_task({"concept": "repulsion"}, [{"input": grid, "output": out}])


def _trajectory_continuation() -> Task:
    h, w = 10, 10
    grid = new_grid(h, w, 0)
    color = random_color()
    for c in range(2, 6):
        grid[4][c] = color
    out = copy_grid(grid)
    for c in range(6, 9):
        out[4][c] = color
    return _base_task({"concept": "trajectory_continuation"}, [{"input": grid, "output": out}])


def _bouncing() -> Task:
    h, w = 10, 10
    grid = new_grid(h, w, 0)
    wall = 8
    for r in range(h):
        grid[r][0] = wall
        grid[r][w - 1] = wall
    for c in range(w):
        grid[0][c] = wall
        grid[h - 1][c] = wall
    start = (2, 2)
    color = random_color(exclude=(0, wall))
    grid[start[0]][start[1]] = color
    out = copy_grid(grid)
    for i in range(2, 8):
        out[i][i] = color
    for i in range(2, 8):
        out[8 - (i - 2)][i] = color
    return _base_task({"concept": "bouncing"}, [{"input": grid, "output": out}])


# ---------------- Category C ----------------

def _hole_filling() -> Task:
    h, w = 10, 10
    grid = new_grid(h, w, 0)
    ring = random_color()
    fill = random_color(exclude=(0, ring))
    place_rect_border(grid, 2, 2, 6, 6, ring)
    out = copy_grid(grid)
    for r in range(3, 7):
        for c in range(3, 7):
            out[r][c] = fill
    return _base_task({"concept": "hole_filling"}, [{"input": grid, "output": out}])


def _enclosure_coloring() -> Task:
    h, w = 10, 10
    grid = new_grid(h, w, 0)
    ring = random_color()
    inner = random_color(exclude=(0, ring))
    target = random_color(exclude=(0, ring, inner))
    place_rect_border(grid, 2, 2, 6, 6, ring)
    place_rect(grid, 4, 4, 2, 2, inner)
    out = copy_grid(grid)
    place_rect_border(out, 2, 2, 6, 6, target)
    return _base_task({"concept": "enclosure_coloring"}, [{"input": grid, "output": out}])


def _connect_points() -> Task:
    h, w = 10, 10
    grid = new_grid(h, w, 0)
    color = random_color()
    a = (2, 2)
    b = (7, 7)
    grid[a[0]][a[1]] = color
    grid[b[0]][b[1]] = color
    out = copy_grid(grid)
    _draw_line(out, a, b, color)
    return _base_task({"concept": "connect_points"}, [{"input": grid, "output": out}])


def _shortest_path() -> Task:
    h, w = 10, 10
    grid = new_grid(h, w, 0)
    start, goal = (1, 1), (8, 8)
    obstacle = 9
    for r in range(3, 7):
        grid[r][5] = obstacle
    grid[start[0]][start[1]] = 1
    grid[goal[0]][goal[1]] = 2
    path = _bfs_path(grid, start, goal, obstacle)
    out = copy_grid(grid)
    for r, c in path:
        if out[r][c] == 0:
            out[r][c] = 3
    return _base_task({"concept": "shortest_path"}, [{"input": grid, "output": out}])


def _count_islands() -> Task:
    h, w = 8, 8
    grid = new_grid(h, w, 0)
    color = random_color()
    points = [(1, 1), (1, 6), (6, 1), (6, 6)]
    for r, c in random.sample(points, k=3):
        grid[r][c] = color
    count = len(_components(grid, color))
    out = new_grid(1, count, color)
    return _base_task({"concept": "count_islands"}, [{"input": grid, "output": out}])


def _remove_singles() -> Task:
    h, w = 10, 10
    grid = new_grid(h, w, 0)
    color = random_color()
    for _ in range(4):
        grid[random.randint(1, 8)][random.randint(1, 8)] = color
    place_rect(grid, 2, 2, 2, 2, color)
    out = copy_grid(grid)
    for r in range(h):
        for c in range(w):
            if out[r][c] == color:
                if all(grid[nr][nc] != color for nr, nc in _neighbors(h, w, r, c)):
                    out[r][c] = 0
    return _base_task({"concept": "remove_singles"}, [{"input": grid, "output": out}])


def _keep_largest() -> Task:
    h, w = 10, 10
    grid = new_grid(h, w, 0)
    color = random_color()
    place_rect(grid, 1, 1, 2, 2, color)
    place_rect(grid, 6, 6, 3, 3, color)
    comps = _components(grid, color)
    largest = max(comps, key=len)
    out = new_grid(h, w, 0)
    for r, c in largest:
        out[r][c] = color
    return _base_task({"concept": "keep_largest"}, [{"input": grid, "output": out}])


def _outline_drawing() -> Task:
    h, w = 10, 10
    grid = new_grid(h, w, 0)
    color = random_color()
    place_rect(grid, 3, 3, 4, 4, color)
    out = new_grid(h, w, 0)
    place_rect_border(out, 3, 3, 4, 4, color)
    return _base_task({"concept": "outline_drawing"}, [{"input": grid, "output": out}])


def _skeletonize() -> Task:
    h, w = 10, 10
    grid = new_grid(h, w, 0)
    color = random_color()
    place_rect(grid, 2, 2, 6, 6, color)
    out = new_grid(h, w, 0)
    mid = 2 + 6 // 2
    for c in range(2, 8):
        out[mid][c] = color
    for r in range(2, 8):
        out[r][mid] = color
    return _base_task({"concept": "skeletonize"}, [{"input": grid, "output": out}])


# ---------------- Category D ----------------

def _color_permutation() -> Task:
    h, w = 8, 8
    grid = new_grid(h, w, 0)
    colors = random.sample([1, 2, 3, 4, 5, 6, 7, 8, 9], 3)
    place_rect(grid, 1, 1, 2, 2, colors[0])
    place_rect(grid, 1, 5, 2, 2, colors[1])
    place_rect(grid, 5, 3, 2, 2, colors[2])
    mapping = {colors[0]: colors[1], colors[1]: colors[2], colors[2]: colors[0]}
    out = new_grid(h, w, 0)
    for r in range(h):
        for c in range(w):
            val = grid[r][c]
            out[r][c] = mapping.get(val, val)
    return _base_task({"concept": "color_permutation"}, [{"input": grid, "output": out}])


def _color_by_size() -> Task:
    h, w = 10, 10
    grid = new_grid(h, w, 0)
    base = random_color()
    place_rect(grid, 1, 1, 2, 2, base)
    place_rect(grid, 6, 6, 3, 3, base)
    comps = _components(grid, base)
    out = new_grid(h, w, 0)
    for comp in comps:
        color = 1 if len(comp) <= 4 else 2
        for r, c in comp:
            out[r][c] = color
    return _base_task({"concept": "color_by_size"}, [{"input": grid, "output": out}])


def _color_by_position() -> Task:
    h, w = 10, 10
    grid = new_grid(h, w, 0)
    color = random_color()
    place_rect(grid, 2, 1, 2, 2, color)
    place_rect(grid, 2, 7, 2, 2, color)
    out = new_grid(h, w, 0)
    for r in range(h):
        for c in range(w):
            if grid[r][c] == color:
                out[r][c] = 1 if c < w // 2 else 2
    return _base_task({"concept": "color_by_position"}, [{"input": grid, "output": out}])


def _boolean_xor() -> Task:
    h, w = 8, 8
    grid = new_grid(h, w, 0)
    a, b = 3, 4
    place_rect(grid, 1, 1, 3, 3, a)
    place_rect(grid, 3, 3, 3, 3, b)
    out = new_grid(h, w, 0)
    for r in range(h):
        for c in range(w):
            av = grid[r][c] == a
            bv = grid[r][c] == b
            if av ^ bv:
                out[r][c] = 5
    return _base_task({"concept": "boolean_xor"}, [{"input": grid, "output": out}])


def _boolean_and() -> Task:
    h, w = 8, 8
    grid = new_grid(h, w, 0)
    a, b = 3, 4
    rect_a = (1, 1, 3, 3)
    rect_b = (2, 2, 3, 3)
    place_rect(grid, *rect_a, a)
    place_rect(grid, *rect_b, b)
    out = new_grid(h, w, 0)
    a_top, a_left, a_h, a_w = rect_a
    b_top, b_left, b_h, b_w = rect_b
    inter_top = max(a_top, b_top)
    inter_left = max(a_left, b_left)
    inter_bottom = min(a_top + a_h, b_top + b_h)
    inter_right = min(a_left + a_w, b_left + b_w)
    if inter_top < inter_bottom and inter_left < inter_right:
        place_rect(out, inter_top, inter_left, inter_bottom - inter_top, inter_right - inter_left, 5)
    return _base_task({"concept": "boolean_and"}, [{"input": grid, "output": out}])


def _dominance() -> Task:
    h, w = 8, 8
    grid = new_grid(h, w, 0)
    bottom, top = 2, 7
    place_rect(grid, 1, 1, 4, 4, bottom)
    place_rect(grid, 3, 3, 3, 3, top)
    out = copy_grid(grid)
    for r in range(h):
        for c in range(w):
            if grid[r][c] == bottom:
                if any(grid[nr][nc] == top for nr, nc in _neighbors(h, w, r, c)):
                    out[r][c] = top
    return _base_task({"concept": "dominance"}, [{"input": grid, "output": out}])


def _palette_reduction() -> Task:
    h, w = 8, 8
    grid = new_grid(h, w, 0)
    for _ in range(6):
        grid[random.randint(0, h - 1)][random.randint(0, w - 1)] = random_color()
    out = new_grid(h, w, 0)
    for r in range(h):
        for c in range(w):
            out[r][c] = 1 if grid[r][c] != 0 else 0
    return _base_task({"concept": "palette_reduction"}, [{"input": grid, "output": out}])


# ---------------- Category E ----------------

def _sorting_size() -> Task:
    h, w = 8, 12
    grid = new_grid(h, w, 0)
    color = random_color()
    place_rect(grid, 1, 1, 2, 2, color)
    place_rect(grid, 4, 1, 3, 3, color)
    comps = sorted(_components(grid, color), key=len)
    out = new_grid(h, w, 0)
    start = 1
    for comp in comps:
        minr, minc, maxr, maxc = _bbox(comp)
        height = maxr - minr + 1
        width = maxc - minc + 1
        place_rect(out, 1, start, height, width, color)
        start += width + 1
    return _base_task({"concept": "sorting_size"}, [{"input": grid, "output": out}])


def _sorting_position() -> Task:
    h, w = 8, 12
    grid = new_grid(h, w, 0)
    color = random_color()
    place_rect(grid, 1, 8, 2, 2, color)
    place_rect(grid, 4, 2, 2, 2, color)
    comps = sorted(_components(grid, color), key=lambda comp: min(c for _, c in comp))
    out = new_grid(h, w, 0)
    start = 1
    for comp in comps:
        minr, minc, maxr, maxc = _bbox(comp)
        height = maxr - minr + 1
        width = maxc - minc + 1
        place_rect(out, 1, start, height, width, color)
        start += width + 1
    return _base_task({"concept": "sorting_position"}, [{"input": grid, "output": out}])


def _histogram() -> Task:
    h, w = 8, 8
    grid = new_grid(h, w, 0)
    colors = [1, 2, 3]
    for col in colors:
        for _ in range(random.randint(1, 4)):
            grid[random.randint(0, h - 1)][random.randint(0, w - 1)] = col
    out = new_grid(h, w, 0)
    for idx, col in enumerate(colors):
        count = sum(1 for r in range(h) for c in range(w) if grid[r][c] == col)
        for r in range(h - 1, h - 1 - count, -1):
            out[r][idx] = col
    return _base_task({"concept": "histogram"}, [{"input": grid, "output": out}])


def _sequence_continuation() -> Task:
    h, w = 10, 10
    grid = new_grid(h, w, 0)
    color = random_color()
    place_rect(grid, 1, 1, 1, 1, color)
    place_rect(grid, 1, 3, 2, 2, color)
    place_rect(grid, 1, 6, 3, 3, color)
    out = copy_grid(grid)
    place_rect(out, 5, 1, 4, 4, color)
    return _base_task({"concept": "sequence_continuation"}, [{"input": grid, "output": out}])


def _binary_counting() -> Task:
    h, w = 6, 10
    grid = new_grid(h, w, 0)
    color = random_color()
    for _ in range(5):
        grid[random.randint(0, h - 1)][random.randint(0, w - 1)] = color
    count = sum(1 for r in range(h) for c in range(w) if grid[r][c] == color)
    bits = list(bin(count)[2:])
    out = new_grid(1, len(bits), 0)
    for i, b in enumerate(bits):
        out[0][i] = 1 if b == "1" else 0
    return _base_task({"concept": "binary_counting"}, [{"input": grid, "output": out}])


MECHANICS: Dict[str, Callable[[], Task]] = {
    "reflection_x": _reflection_x,
    "reflection_y": _reflection_y,
    "rotation_90": _rotation_90,
    "rotation_180": _rotation_180,
    "tiling": _tiling,
    "crop_to_content": _crop_to_content,
    "upscale_2x": _upscale_2x,
    "downscale_2x": _downscale_2x,
    "symmetry_completion": _symmetry_completion,
    "axis_alignment": _axis_alignment,
    "gravity_drop": lambda: _gravity_drop("down"),
    "gravity_up": lambda: _gravity_drop("up"),
    "gravity_left": lambda: _gravity_drop("left"),
    "gravity_right": lambda: _gravity_drop("right"),
    "object_collision": _object_collision,
    "sliding_puzzle": _sliding_puzzle,
    "magnetism": _magnetism,
    "repulsion": _repulsion,
    "trajectory_continuation": _trajectory_continuation,
    "bouncing": _bouncing,
    "hole_filling": _hole_filling,
    "enclosure_coloring": _enclosure_coloring,
    "connect_points": _connect_points,
    "shortest_path": _shortest_path,
    "count_islands": _count_islands,
    "remove_singles": _remove_singles,
    "keep_largest": _keep_largest,
    "outline_drawing": _outline_drawing,
    "skeletonize": _skeletonize,
    "color_permutation": _color_permutation,
    "color_by_size": _color_by_size,
    "color_by_position": _color_by_position,
    "boolean_xor": _boolean_xor,
    "boolean_and": _boolean_and,
    "dominance": _dominance,
    "palette_reduction": _palette_reduction,
    "sorting_size": _sorting_size,
    "sorting_position": _sorting_position,
    "histogram": _histogram,
    "sequence_continuation": _sequence_continuation,
    "binary_counting": _binary_counting,
}


def generate(concept: str | None = None, seed: int | None = None) -> Task:
    if seed is not None:
        random.seed(seed)
    if concept is None:
        concept = random.choice(list(MECHANICS.keys()))
    if concept not in MECHANICS:
        raise ValueError(f"Unknown mechanic: {concept}")
    task = MECHANICS[concept]()
    task["meta"].update({"chapter": "multi", "generator": "mechanics", "concept": concept})
    return task
