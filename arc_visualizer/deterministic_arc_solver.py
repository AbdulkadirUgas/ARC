#!/usr/bin/env python3
"""Deterministic ARC solver using exact train-pair rule verification."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

import score_submission_by_taxonomy as scorer
import tag_arc_tasks as tags

Grid = list[list[int]]
Pair = dict[str, Grid]
Task = dict[str, list[Pair]]


@dataclass
class RuleCandidate:
    name: str
    family: str
    priority: int
    apply: Callable[[Grid], Grid | None]
    metadata: dict[str, object] = field(default_factory=dict)
    train_correct: int = 0
    train_total: int = 0


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_output_dir() -> Path:
    return repo_root() / "local_runs" / "deterministic_arc_solver"


def load_json(path: Path):
    with path.open() as f:
        return json.load(f)


def dump_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2)


def append_jsonl(path: Path, row: dict) -> None:
    with path.open("a") as f:
        f.write(json.dumps(row) + "\n")


def copy_grid(grid: Grid) -> Grid:
    return [row[:] for row in grid]


def normalize_grid(grid: Grid) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(cell) for cell in row) for row in grid)


def grid_equal(a: Grid | None, b: Grid) -> bool:
    return a is not None and normalize_grid(a) == normalize_grid(b)


def valid_grid(grid: Grid | None) -> bool:
    if not isinstance(grid, list) or not grid:
        return False
    if not all(isinstance(row, list) and row for row in grid):
        return False
    width = len(grid[0])
    if len(grid) > 30 or width > 30:
        return False
    for row in grid:
        if len(row) != width:
            return False
        for cell in row:
            if not isinstance(cell, int) or not (0 <= cell <= 9):
                return False
    return True


def shape(grid: Grid) -> tuple[int, int]:
    return len(grid), len(grid[0]) if grid else 0


def flatten(grid: Grid) -> list[int]:
    return [cell for row in grid for cell in row]


def all_colors(grid: Grid) -> list[int]:
    return sorted(set(flatten(grid)))


def background_color(grid: Grid) -> int:
    return tags.most_common_color(grid)


def non_bg_colors_by_frequency(grid: Grid) -> list[int]:
    bg = background_color(grid)
    counts = Counter(cell for cell in flatten(grid) if cell != bg)
    return [
        color
        for color, _ in sorted(
            counts.items(),
            key=lambda item: (item[1], item[0]),
        )
    ]


def color_locations(grid: Grid, color: int) -> list[tuple[int, int]]:
    return [(r, c) for r, row in enumerate(grid) for c, cell in enumerate(row) if cell == color]


def bbox_of_color(grid: Grid, color: int) -> tuple[int, int, int, int] | None:
    coords = color_locations(grid, color)
    if not coords:
        return None
    rows = [r for r, _ in coords]
    cols = [c for _, c in coords]
    return min(rows), max(rows), min(cols), max(cols)


def crop_box(grid: Grid, box: tuple[int, int, int, int]) -> Grid:
    r0, r1, c0, c1 = box
    return [row[c0 : c1 + 1] for row in grid[r0 : r1 + 1]]


def crop_with_margins(grid: Grid, top: int, bottom: int, left: int, right: int) -> Grid | None:
    h, w = shape(grid)
    if top + bottom >= h or left + right >= w:
        return None
    return [row[left : w - right] for row in grid[top : h - bottom]]


def zero_grid(height: int, width: int, fill: int = 0) -> Grid:
    return [[fill for _ in range(width)] for _ in range(height)]


def transpose(grid: Grid) -> Grid:
    return [list(row) for row in zip(*grid)]


def dedupe_consecutive_rows(grid: Grid) -> Grid:
    rows = []
    prev = None
    for row in grid:
        if row != prev:
            rows.append(row[:])
            prev = row
    return rows


def dedupe_consecutive_cols(grid: Grid) -> Grid:
    return transpose(dedupe_consecutive_rows(transpose(grid)))


def dedupe_rows_keep_first(grid: Grid) -> Grid:
    seen = set()
    rows = []
    for row in grid:
        key = tuple(row)
        if key in seen:
            continue
        seen.add(key)
        rows.append(row[:])
    return rows


def dedupe_cols_keep_first(grid: Grid) -> Grid:
    return transpose(dedupe_rows_keep_first(transpose(grid)))


def remove_all_bg_rows(grid: Grid) -> Grid:
    bg = background_color(grid)
    rows = [row[:] for row in grid if any(cell != bg for cell in row)]
    return rows or copy_grid(grid)


def remove_all_bg_cols(grid: Grid) -> Grid:
    return transpose(remove_all_bg_rows(transpose(grid)))


def remove_uniform_color_rows(grid: Grid, color: int) -> Grid:
    rows = [row[:] for row in grid if any(cell != color for cell in row)]
    return rows or copy_grid(grid)


def remove_uniform_color_cols(grid: Grid, color: int) -> Grid:
    return transpose(remove_uniform_color_rows(transpose(grid), color))


def all_subgrid_margin_positions(inp: Grid, out: Grid) -> list[tuple[int, int, int, int]]:
    ih, iw = shape(inp)
    oh, ow = shape(out)
    matches = []
    if oh > ih or ow > iw:
        return matches
    for r0 in range(ih - oh + 1):
        for c0 in range(iw - ow + 1):
            if inp[r0 : r0 + oh] and all(
                inp[r0 + rr][c0 : c0 + ow] == out[rr] for rr in range(oh)
            ):
                matches.append((r0, ih - (r0 + oh), c0, iw - (c0 + ow)))
    return matches


def connected_components(grid: Grid, bg: int | None = None) -> list[dict[str, object]]:
    if bg is None:
        bg = background_color(grid)
    h, w = shape(grid)
    seen = [[False] * w for _ in range(h)]
    comps = []
    for r in range(h):
        for c in range(w):
            color = grid[r][c]
            if seen[r][c] or color == bg:
                continue
            stack = [(r, c)]
            seen[r][c] = True
            cells: list[tuple[int, int]] = []
            while stack:
                cr, cc = stack.pop()
                cells.append((cr, cc))
                for nr, nc in ((cr - 1, cc), (cr + 1, cc), (cr, cc - 1), (cr, cc + 1)):
                    if 0 <= nr < h and 0 <= nc < w and not seen[nr][nc] and grid[nr][nc] == color:
                        seen[nr][nc] = True
                        stack.append((nr, nc))
            rows = [x for x, _ in cells]
            cols = [y for _, y in cells]
            comps.append(
                {
                    "color": color,
                    "size": len(cells),
                    "cells": cells,
                    "bbox": (min(rows), max(rows), min(cols), max(cols)),
                }
            )
    return comps


def component_to_grid(grid: Grid, component: dict[str, object], fill_mode: str) -> Grid:
    r0, r1, c0, c1 = component["bbox"]  # type: ignore[index]
    if fill_mode == "original_bg":
        fill = background_color(grid)
    else:
        fill = 0
    out = zero_grid(r1 - r0 + 1, c1 - c0 + 1, fill)
    for r, c in component["cells"]:  # type: ignore[index]
        out[r - r0][c - c0] = grid[r][c]
    return out


def bbox_crop_for_selector(grid: Grid, selector: Callable[[Grid], int | None]) -> Grid | None:
    color = selector(grid)
    if color is None:
        return None
    box = bbox_of_color(grid, color)
    if box is None:
        return None
    return crop_box(grid, box)


def color_mask_crop_for_selector(
    grid: Grid,
    selector: Callable[[Grid], int | None],
    fill_mode: str,
) -> Grid | None:
    color = selector(grid)
    if color is None:
        return None
    box = bbox_of_color(grid, color)
    if box is None:
        return None
    fill = background_color(grid) if fill_mode == "original_bg" else 0
    cropped = crop_box(grid, box)
    return [[cell if cell == color else fill for cell in row] for row in cropped]


def apply_color_map(grid: Grid, mapping: dict[int, int]) -> Grid | None:
    out = []
    for row in grid:
        mapped_row = []
        for cell in row:
            if cell not in mapping:
                return None
            mapped_row.append(mapping[cell])
        out.append(mapped_row)
    return out


def swap_bg_with_selected_non_bg(grid: Grid, selector: Callable[[Grid], int | None]) -> Grid | None:
    bg = background_color(grid)
    selected = selector(grid)
    if selected is None:
        return None
    mapping = {bg: selected, selected: bg}
    out = []
    for row in grid:
        out.append([mapping.get(cell, cell) for cell in row])
    return out


def recolor_non_bg_to_selected(grid: Grid, selector: Callable[[Grid], int | None]) -> Grid | None:
    bg = background_color(grid)
    selected = selector(grid)
    if selected is None:
        return None
    return [[selected if cell != bg else bg for cell in row] for row in grid]


def overlay_with_transform(grid: Grid, transform_name: str) -> Grid:
    bg = background_color(grid)
    transformed = tags.TRANSFORMS[transform_name](grid)
    if shape(transformed) != shape(grid):
        return None
    out = copy_grid(grid)
    for r in range(len(out)):
        for c in range(len(out[0])):
            if out[r][c] == bg and transformed[r][c] != bg:
                out[r][c] = transformed[r][c]
    return out


def shared_color_map_for_preprocessor(
    train: list[Pair],
    preprocess: Callable[[Grid], Grid | None],
) -> dict[int, int] | None:
    mapping: dict[int, int] = {}
    for pair in train:
        pre = preprocess(pair["input"])
        if pre is None or shape(pre) != shape(pair["output"]):
            return None
        local_map = tags.color_map_if_exists(pre, pair["output"])
        if local_map is None:
            return None
        for src, dst in local_map.items():
            if src in mapping and mapping[src] != dst:
                return None
            mapping[src] = dst
    return mapping


def make_selector_functions() -> list[tuple[str, Callable[[Grid], int | None]]]:
    def least_freq_non_bg(grid: Grid) -> int | None:
        colors = non_bg_colors_by_frequency(grid)
        return colors[0] if colors else None

    def most_freq_non_bg(grid: Grid) -> int | None:
        colors = non_bg_colors_by_frequency(grid)
        return colors[-1] if colors else None

    def top_left_non_bg(grid: Grid) -> int | None:
        bg = background_color(grid)
        for row in grid:
            for cell in row:
                if cell != bg:
                    return cell
        return None

    def top_right_non_bg(grid: Grid) -> int | None:
        bg = background_color(grid)
        for row in grid:
            for cell in reversed(row):
                if cell != bg:
                    return cell
        return None

    def bottom_left_non_bg(grid: Grid) -> int | None:
        bg = background_color(grid)
        for row in reversed(grid):
            for cell in row:
                if cell != bg:
                    return cell
        return None

    def bottom_right_non_bg(grid: Grid) -> int | None:
        bg = background_color(grid)
        for row in reversed(grid):
            for cell in reversed(row):
                if cell != bg:
                    return cell
        return None

    return [
        ("least_freq_non_bg", least_freq_non_bg),
        ("most_freq_non_bg", most_freq_non_bg),
        ("top_left_non_bg", top_left_non_bg),
        ("top_right_non_bg", top_right_non_bg),
        ("bottom_left_non_bg", bottom_left_non_bg),
        ("bottom_right_non_bg", bottom_right_non_bg),
    ]


def select_component(grid: Grid, selector_name: str) -> dict[str, object] | None:
    comps = connected_components(grid)
    if not comps:
        return None

    def key_top_left(comp):
        r0, r1, c0, c1 = comp["bbox"]
        return (r0, c0, r1, c1, -comp["size"], comp["color"])

    def key_bottom_right(comp):
        r0, r1, c0, c1 = comp["bbox"]
        return (-r1, -c1, -r0, -c0, -comp["size"], comp["color"])

    orders = {
        "largest": sorted(comps, key=lambda comp: (-comp["size"], key_top_left(comp))),
        "smallest": sorted(comps, key=lambda comp: (comp["size"], key_top_left(comp))),
        "topmost": sorted(comps, key=lambda comp: key_top_left(comp)),
        "leftmost": sorted(comps, key=lambda comp: (comp["bbox"][2], comp["bbox"][0], -comp["size"], comp["color"])),
        "rightmost": sorted(comps, key=lambda comp: (-comp["bbox"][3], comp["bbox"][0], -comp["size"], comp["color"])),
        "bottommost": sorted(comps, key=lambda comp: (-comp["bbox"][1], comp["bbox"][2], -comp["size"], comp["color"])),
        "top_left": sorted(comps, key=lambda comp: key_top_left(comp)),
        "bottom_right": sorted(comps, key=lambda comp: key_bottom_right(comp)),
    }
    picked = orders.get(selector_name)
    return picked[0] if picked else None


def block_reduce(grid: Grid, row_factor: int, col_factor: int, reducer: str) -> Grid | None:
    h, w = shape(grid)
    if h % row_factor != 0 or w % col_factor != 0:
        return None
    out_h = h // row_factor
    out_w = w // col_factor
    out = []
    for r in range(out_h):
        row = []
        for c in range(out_w):
            block = [
                grid[rr][cc]
                for rr in range(r * row_factor, (r + 1) * row_factor)
                for cc in range(c * col_factor, (c + 1) * col_factor)
            ]
            if reducer == "top_left":
                value = grid[r * row_factor][c * col_factor]
            elif reducer == "top_right":
                value = grid[r * row_factor][(c + 1) * col_factor - 1]
            elif reducer == "bottom_left":
                value = grid[(r + 1) * row_factor - 1][c * col_factor]
            elif reducer == "bottom_right":
                value = grid[(r + 1) * row_factor - 1][(c + 1) * col_factor - 1]
            elif reducer == "center":
                value = grid[r * row_factor + row_factor // 2][c * col_factor + col_factor // 2]
            elif reducer == "majority":
                counts = Counter(block)
                value = max(counts.items(), key=lambda item: (item[1], -item[0]))[0]
            elif reducer == "minority_non_bg":
                bg = background_color([block])
                counts = Counter(cell for cell in block if cell != bg)
                if not counts:
                    value = bg
                else:
                    value = min(counts.items(), key=lambda item: (item[1], item[0]))[0]
            elif reducer == "unique_non_bg":
                bg = background_color([block])
                colors = sorted({cell for cell in block if cell != bg})
                if len(colors) == 1:
                    value = colors[0]
                elif len(colors) == 0:
                    value = bg
                else:
                    return None
            else:
                return None
            row.append(int(value))
        out.append(row)
    return out


def repeat_cells(grid: Grid, row_factor: int, col_factor: int) -> Grid:
    out = []
    for row in grid:
        expanded = [cell for cell in row for _ in range(col_factor)]
        for _ in range(row_factor):
            out.append(expanded[:])
    return out


def tile_grid(grid: Grid, out_h: int, out_w: int) -> Grid | None:
    h, w = shape(grid)
    if h == 0 or w == 0 or out_h % h != 0 or out_w % w != 0:
        return None
    return [[grid[r % h][c % w] for c in range(out_w)] for r in range(out_h)]


def sampling_subgrid(grid: Grid, row_offset: int, row_step: int, col_offset: int, col_step: int) -> Grid | None:
    sampled_rows = grid[row_offset::row_step]
    if not sampled_rows:
        return None
    sampled = [row[col_offset::col_step] for row in sampled_rows]
    return sampled if valid_grid(sampled) else None


def rule_from_transform(name: str) -> RuleCandidate:
    return RuleCandidate(
        name=f"transform:{name}",
        family="global_transform",
        priority=10,
        apply=lambda grid, fn=tags.TRANSFORMS[name]: fn(grid),
        metadata={"transform": name},
    )


def infer_shared_margin_crop_rules(train: list[Pair]) -> list[RuleCandidate]:
    shared_positions = None
    for pair in train:
        positions = set(all_subgrid_margin_positions(pair["input"], pair["output"]))
        if not positions:
            return []
        shared_positions = positions if shared_positions is None else shared_positions.intersection(positions)
        if not shared_positions:
            return []
    rules = []
    for margins in sorted(shared_positions):
        top, bottom, left, right = margins
        rules.append(
            RuleCandidate(
                name=f"margin_crop:t{top}:b{bottom}:l{left}:r{right}",
                family="margin_crop",
                priority=25,
                apply=lambda grid, m=margins: crop_with_margins(grid, *m),
                metadata={"margins": margins},
            )
        )
    return rules


def infer_block_reduce_rules(train: list[Pair]) -> list[RuleCandidate]:
    reducers = [
        "top_left",
        "top_right",
        "bottom_left",
        "bottom_right",
        "center",
        "majority",
        "minority_non_bg",
        "unique_non_bg",
    ]
    factor_sets = []
    for pair in train:
        ih, iw = shape(pair["input"])
        oh, ow = shape(pair["output"])
        if oh == 0 or ow == 0 or ih % oh != 0 or iw % ow != 0:
            return []
        factor_sets.append((ih // oh, iw // ow))
    if len(set(factor_sets)) != 1:
        return []
    row_factor, col_factor = factor_sets[0]
    if row_factor == 1 and col_factor == 1:
        return []
    return [
        RuleCandidate(
            name=f"block_reduce:{reducer}:{row_factor}x{col_factor}",
            family="block_reduce",
            priority=40,
            apply=lambda grid, rf=row_factor, cf=col_factor, red=reducer: block_reduce(grid, rf, cf, red),
            metadata={"row_factor": row_factor, "col_factor": col_factor, "reducer": reducer},
        )
        for reducer in reducers
    ]


def infer_repeat_rules(train: list[Pair]) -> list[RuleCandidate]:
    factors = []
    for pair in train:
        ih, iw = shape(pair["input"])
        oh, ow = shape(pair["output"])
        if ih == 0 or iw == 0 or oh % ih != 0 or ow % iw != 0:
            return []
        factors.append((oh // ih, ow // iw))
    if len(set(factors)) != 1:
        return []
    row_factor, col_factor = factors[0]
    if row_factor == 1 and col_factor == 1:
        return []
    return [
        RuleCandidate(
            name=f"repeat_cells:{row_factor}x{col_factor}",
            family="repeat_cells",
            priority=45,
            apply=lambda grid, rf=row_factor, cf=col_factor: repeat_cells(grid, rf, cf),
            metadata={"row_factor": row_factor, "col_factor": col_factor},
        )
    ]


def infer_tile_rules(train: list[Pair]) -> list[RuleCandidate]:
    rules = []
    factors = []
    for pair in train:
        ih, iw = shape(pair["input"])
        oh, ow = shape(pair["output"])
        if ih == 0 or iw == 0 or oh % ih != 0 or ow % iw != 0:
            return []
        factors.append((oh // ih, ow // iw))
    if len(set(factors)) != 1:
        return []
    row_factor, col_factor = factors[0]

    selector_fns = {name: fn for name, fn in make_selector_functions()}
    preprocessors: list[tuple[str, Callable[[Grid], Grid | None]]] = []
    for transform_name in tags.TRANSFORMS:
        preprocessors.append(
            (
                f"transform:{transform_name}",
                lambda grid, n=transform_name: tags.TRANSFORMS[n](grid),
            )
        )
        for selector_name, selector in selector_fns.items():
            preprocessors.append(
                (
                    f"transform:{transform_name}:swap_bg_with:{selector_name}",
                    lambda grid, n=transform_name, s=selector: swap_bg_with_selected_non_bg(tags.TRANSFORMS[n](grid), s),
                )
            )

    for preprocess_name, preprocess in preprocessors:
        matches = True
        for pair in train:
            base = preprocess(pair["input"])
            if base is None:
                matches = False
                break
            ih, iw = shape(base)
            tiled = tile_grid(base, ih * row_factor, iw * col_factor)
            if not grid_equal(tiled, pair["output"]):
                matches = False
                break
        if matches:
            rules.append(
                RuleCandidate(
                    name=f"tile:{preprocess_name}:{row_factor}x{col_factor}",
                    family="tile_repeat",
                    priority=50,
                    apply=lambda grid, fn=preprocess, rf=row_factor, cf=col_factor: tile_grid(
                        fn(grid),
                        shape(fn(grid))[0] * rf,
                        shape(fn(grid))[1] * cf,
                    )
                    if fn(grid) is not None
                    else None,
                    metadata={"preprocess": preprocess_name, "factors": [row_factor, col_factor]},
                )
            )
            continue

        mapping = {}
        mapping_ok = True
        for pair in train:
            base = preprocess(pair["input"])
            if base is None:
                mapping_ok = False
                break
            local_map = tags.color_tile_map_if_exists(
                base,
                pair["output"],
            )
            if local_map is None:
                mapping_ok = False
                break
            for src, dst in local_map.items():
                if src in mapping and mapping[src] != dst:
                    mapping_ok = False
                    break
                mapping[src] = dst
            if not mapping_ok:
                break
        if mapping_ok and mapping:
            rules.append(
                RuleCandidate(
                    name=f"tile_color_map:{preprocess_name}:{row_factor}x{col_factor}",
                    family="tile_repeat_color_map",
                    priority=52,
                    apply=lambda grid, fn=preprocess, rf=row_factor, cf=col_factor, m=mapping: apply_color_map(
                        tile_grid(
                            fn(grid),
                            shape(fn(grid))[0] * rf,
                            shape(fn(grid))[1] * cf,
                        ),
                        m,
                    )
                    if fn(grid) is not None
                    else None,
                    metadata={"preprocess": preprocess_name, "factors": [row_factor, col_factor], "color_map": mapping},
                )
            )
    return rules


def infer_stride_sampling_rules(train: list[Pair]) -> list[RuleCandidate]:
    if not train:
        return []
    first_in_h, first_in_w = shape(train[0]["input"])
    rules = []
    for transform_name in tags.TRANSFORMS:
        for row_step in range(2, min(first_in_h, 8) + 1):
            for col_step in range(2, min(first_in_w, 8) + 1):
                for row_offset in range(row_step):
                    for col_offset in range(col_step):
                        ok = True
                        for pair in train:
                            transformed = tags.TRANSFORMS[transform_name](pair["input"])
                            sampled = sampling_subgrid(transformed, row_offset, row_step, col_offset, col_step)
                            if not grid_equal(sampled, pair["output"]):
                                ok = False
                                break
                        if ok:
                            rules.append(
                                RuleCandidate(
                                    name=f"stride_sample:{transform_name}:r{row_offset}/{row_step}:c{col_offset}/{col_step}",
                                    family="stride_sample",
                                    priority=60,
                                    apply=lambda grid, n=transform_name, ro=row_offset, rs=row_step, co=col_offset, cs=col_step: sampling_subgrid(
                                        tags.TRANSFORMS[n](grid),
                                        ro,
                                        rs,
                                        co,
                                        cs,
                                    ),
                                    metadata={
                                        "transform": transform_name,
                                        "row_offset": row_offset,
                                        "row_step": row_step,
                                        "col_offset": col_offset,
                                        "col_step": col_step,
                                    },
                                )
                            )
    return rules


def base_rule_candidates(train: list[Pair]) -> list[RuleCandidate]:
    rules = [rule_from_transform(name) for name in tags.TRANSFORMS]

    rules.append(
        RuleCandidate(
            name="crop_foreground_bbox",
            family="crop_foreground_bbox",
            priority=20,
            apply=lambda grid: crop_box(grid, tags.bbox_of_non_bg(grid, background_color(grid)))
            if tags.bbox_of_non_bg(grid, background_color(grid)) is not None
            else None,
        )
    )

    rules.extend(infer_shared_margin_crop_rules(train))

    row_col_pipelines = [
        ("remove_bg_rows", remove_all_bg_rows),
        ("remove_bg_cols", remove_all_bg_cols),
        ("remove_bg_rows_cols", lambda grid: remove_all_bg_cols(remove_all_bg_rows(grid))),
        ("remove_bg_cols_rows", lambda grid: remove_all_bg_rows(remove_all_bg_cols(grid))),
        ("dedupe_rows", dedupe_consecutive_rows),
        ("dedupe_cols", dedupe_consecutive_cols),
        ("dedupe_rows_cols", lambda grid: dedupe_consecutive_cols(dedupe_consecutive_rows(grid))),
        ("dedupe_cols_rows", lambda grid: dedupe_consecutive_rows(dedupe_consecutive_cols(grid))),
        ("unique_rows", dedupe_rows_keep_first),
        ("unique_cols", dedupe_cols_keep_first),
        ("unique_rows_cols", lambda grid: dedupe_cols_keep_first(dedupe_rows_keep_first(grid))),
        ("unique_cols_rows", lambda grid: dedupe_rows_keep_first(dedupe_cols_keep_first(grid))),
        ("remove_bg_rows_then_dedupe_cols", lambda grid: dedupe_consecutive_cols(remove_all_bg_rows(grid))),
        ("remove_bg_cols_then_dedupe_rows", lambda grid: dedupe_consecutive_rows(remove_all_bg_cols(grid))),
    ]
    for name, fn in row_col_pipelines:
        rules.append(RuleCandidate(name=name, family="row_col_filter", priority=30, apply=fn))

    for selector_name, selector in make_selector_functions():
        rules.append(
            RuleCandidate(
                name=f"swap_bg_with:{selector_name}",
                family="dynamic_color_swap",
                priority=34,
                apply=lambda grid, s=selector: swap_bg_with_selected_non_bg(grid, s),
                metadata={"selector": selector_name},
            )
        )
        rules.append(
            RuleCandidate(
                name=f"recolor_non_bg_to:{selector_name}",
                family="dynamic_color_recolor",
                priority=36,
                apply=lambda grid, s=selector: recolor_non_bg_to_selected(grid, s),
                metadata={"selector": selector_name},
            )
        )
        rules.append(
            RuleCandidate(
                name=f"color_bbox:{selector_name}",
                family="color_bbox",
                priority=70,
                apply=lambda grid, s=selector: bbox_crop_for_selector(grid, s),
                metadata={"selector": selector_name, "mode": "bbox_crop"},
            )
        )
        for fill_mode in ("zero_bg", "original_bg"):
            rules.append(
                RuleCandidate(
                    name=f"color_mask:{selector_name}:{fill_mode}",
                    family="color_mask",
                    priority=72,
                    apply=lambda grid, s=selector, fm=fill_mode: color_mask_crop_for_selector(grid, s, fm),
                    metadata={"selector": selector_name, "mode": "mask_crop", "fill_mode": fill_mode},
                )
            )

    component_selectors = ["largest", "smallest", "topmost", "leftmost", "rightmost", "bottommost", "top_left", "bottom_right"]
    for selector_name in component_selectors:
        for fill_mode in ("zero_bg", "original_bg"):
            rules.append(
                RuleCandidate(
                    name=f"component:{selector_name}:{fill_mode}",
                    family="component_extract",
                    priority=80,
                    apply=lambda grid, s=selector_name, fm=fill_mode: component_to_grid(grid, select_component(grid, s), fm)
                    if select_component(grid, s) is not None
                    else None,
                    metadata={"selector": selector_name, "fill_mode": fill_mode},
                )
            )

    rules.extend(infer_block_reduce_rules(train))
    rules.extend(infer_repeat_rules(train))
    rules.extend(infer_tile_rules(train))
    rules.extend(infer_stride_sampling_rules(train))

    for transform_name in ("flip_h", "flip_v", "rot180", "transpose"):
        rules.append(
            RuleCandidate(
                name=f"overlay_with:{transform_name}",
                family="symmetry_overlay",
                priority=38,
                apply=lambda grid, n=transform_name: overlay_with_transform(grid, n),
                metadata={"transform": transform_name},
            )
        )

    return rules


def lift_shared_color_map_rules(train: list[Pair], base_rules: list[RuleCandidate]) -> list[RuleCandidate]:
    lifted = []
    for rule in base_rules:
        mapping = shared_color_map_for_preprocessor(train, rule.apply)
        if mapping is None:
            continue
        lifted.append(
            RuleCandidate(
                name=f"{rule.name}+shared_color_map",
                family=f"{rule.family}_color_map",
                priority=rule.priority + 5,
                apply=lambda grid, fn=rule.apply, m=mapping: apply_color_map(fn(grid), m) if fn(grid) is not None else None,
                metadata={**rule.metadata, "shared_color_map": mapping},
            )
        )
    return lifted


def score_rule_on_train(rule: RuleCandidate, train: list[Pair]) -> RuleCandidate:
    correct = 0
    for pair in train:
        predicted = rule.apply(pair["input"])
        if grid_equal(predicted, pair["output"]):
            correct += 1
    rule.train_correct = correct
    rule.train_total = len(train)
    return rule


def unique_rules_by_name(rules: list[RuleCandidate]) -> list[RuleCandidate]:
    seen = set()
    out = []
    for rule in rules:
        if rule.name in seen:
            continue
        seen.add(rule.name)
        out.append(rule)
    return out


def infer_rules(train: list[Pair]) -> list[RuleCandidate]:
    base = base_rule_candidates(train)
    lifted = lift_shared_color_map_rules(train, base)
    rules = unique_rules_by_name(base + lifted)
    scored = [score_rule_on_train(rule, train) for rule in rules]
    scored.sort(key=lambda rule: (-rule.train_correct, rule.priority, rule.name))
    return scored


def zero_grid_like(grid: Grid) -> Grid:
    h, w = shape(grid)
    return zero_grid(h, w, 0)


def build_attempts(test_grid: Grid, rules: list[RuleCandidate], train_total: int) -> tuple[list[Grid], list[dict[str, object]]]:
    attempts: list[Grid] = []
    sources: list[dict[str, object]] = []
    seen = set()
    ordered = rules[:]
    exact_first = [rule for rule in ordered if rule.train_correct == train_total]
    partial = [rule for rule in ordered if rule.train_correct < train_total]

    for bucket_name, bucket in (("exact", exact_first), ("partial", partial)):
        for rule in bucket:
            predicted = rule.apply(test_grid)
            if not valid_grid(predicted):
                continue
            key = normalize_grid(predicted)
            if key in seen:
                continue
            seen.add(key)
            attempts.append(predicted)
            sources.append(
                {
                    "rule_name": rule.name,
                    "family": rule.family,
                    "bucket": bucket_name,
                    "train_correct": rule.train_correct,
                    "train_total": rule.train_total,
                }
            )
            if len(attempts) == 2:
                return attempts, sources

    if not attempts:
        fallback = zero_grid_like(test_grid)
        attempts.append(fallback)
        sources.append({"rule_name": "zero_grid_like_input", "family": "fallback", "bucket": "fallback"})

    if len(attempts) == 1:
        attempts.append(copy_grid(attempts[0]))
        sources.append(dict(sources[0]))
    return attempts, sources


def summarize_records(records: list[dict]) -> dict:
    total = len(records)
    exact_candidate = sum(bool(record["exact_rule_candidate_count"]) for record in records)
    partial_candidate = sum(bool(record["best_train_rule_correct"] > 0) for record in records)
    return {
        "num_records": total,
        "tasks_with_exact_rule_candidate": exact_candidate,
        "tasks_with_exact_rule_candidate_rate": round(exact_candidate / total, 6) if total else 0.0,
        "tasks_with_partial_rule_candidate": partial_candidate,
        "tasks_with_partial_rule_candidate_rate": round(partial_candidate / total, 6) if total else 0.0,
        "max_best_train_rule_correct": max((record["best_train_rule_correct"] for record in records), default=0),
        "avg_best_train_rule_correct": round(
            sum(record["best_train_rule_correct"] for record in records) / total,
            4,
        )
        if total
        else 0.0,
        "top_rule_names": dict(Counter(record["attempt_sources"][0]["rule_name"] for record in records if record["attempt_sources"]).most_common(20)),
    }


def maybe_score_submission(split_name: str, submission: dict, restrict_task_ids: list[str]) -> dict | None:
    solutions_path = repo_root() / f"arc-agi_{split_name}_solutions.json"
    tags_path = repo_root() / "analysis" / "task_taxonomy" / f"{split_name}_tags.jsonl"
    if not solutions_path.exists() or not tags_path.exists():
        return None
    tags_rows = scorer.load_jsonl(tags_path)
    solutions = scorer.load_json(solutions_path)
    return scorer.score_submission(tags_rows, solutions, submission, restrict_task_ids=restrict_task_ids)


def run_solver(
    data_dir: Path,
    split_name: str,
    output_dir: Path,
    max_tasks: int | None,
) -> dict:
    challenges_path = data_dir / f"arc-agi_{split_name}_challenges.json"
    challenges = load_json(challenges_path)
    task_ids = list(challenges)
    if max_tasks is not None:
        task_ids = task_ids[:max_tasks]

    output_dir.mkdir(parents=True, exist_ok=True)
    task_records_path = output_dir / "task_records.jsonl"
    if task_records_path.exists():
        task_records_path.unlink()

    start = time.time()
    submission = {}
    records = []

    for task_order, task_id in enumerate(task_ids, start=1):
        task = challenges[task_id]
        rules = infer_rules(task["train"])
        train_total = len(task["train"])
        exact_rule_count = sum(rule.train_correct == train_total for rule in rules)
        best_train_rule_correct = max((rule.train_correct for rule in rules), default=0)
        top_rules = [
            {
                "name": rule.name,
                "family": rule.family,
                "train_correct": rule.train_correct,
                "train_total": rule.train_total,
            }
            for rule in rules[:10]
        ]

        submission[task_id] = []
        for test_index, test_pair in enumerate(task["test"]):
            test_start = time.time()
            attempts, sources = build_attempts(test_pair["input"], rules, train_total)
            submission[task_id].append({"attempt_1": attempts[0], "attempt_2": attempts[1]})
            record = {
                "task_id": task_id,
                "task_order": task_order,
                "test_index": test_index,
                "split_name": split_name,
                "rule_version": "deterministic_v1",
                "num_train_examples": train_total,
                "num_rules_considered": len(rules),
                "exact_rule_candidate_count": exact_rule_count,
                "best_train_rule_correct": best_train_rule_correct,
                "top_rules": top_rules,
                "attempt_sources": sources,
                "attempt_shapes": [list(shape(attempts[0])), list(shape(attempts[1]))],
                "elapsed_sec": round(time.time() - test_start, 4),
            }
            records.append(record)
            append_jsonl(task_records_path, record)

    dump_json(output_dir / "submission.json", submission)

    artifact_summary = summarize_records(records)
    score_report = maybe_score_submission(split_name, submission, task_ids)

    result = {
        "run_dir": str(output_dir),
        "config": {
            "data_dir": str(data_dir),
            "split_name": split_name,
            "output_dir": str(output_dir),
            "max_tasks": max_tasks,
            "rule_version": "deterministic_v1",
            "num_tasks_run": len(task_ids),
            "challenge_file": str(challenges_path),
            "total_elapsed_sec": round(time.time() - start, 4),
        },
        "artifact_summary": artifact_summary,
        "score_report": score_report,
    }
    dump_json(output_dir / "local_summary.json", result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=repo_root(),
        help="Directory containing arc-agi_<split>_challenges.json",
    )
    parser.add_argument(
        "--split-name",
        choices=["training", "evaluation", "test"],
        default="evaluation",
    )
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    parser.add_argument("--max-tasks", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_solver(
        data_dir=args.data_dir,
        split_name=args.split_name,
        output_dir=args.output_dir,
        max_tasks=args.max_tasks,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
