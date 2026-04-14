#!/usr/bin/env python3
"""ARC object/program search baseline with targeted slice benchmarking."""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Callable

import deterministic_arc_solver as base
import score_submission_by_taxonomy as scorer
import tag_arc_tasks as tags

Grid = list[list[int]]
Pair = dict[str, Grid]
RuleCandidate = base.RuleCandidate
RULE_VERSION = "object_program_v3"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_output_dir() -> Path:
    return repo_root() / "local_runs" / "object_program_arc_solver"


def load_json(path: Path):
    with path.open() as f:
        return json.load(f)


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def dump_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2)


def append_jsonl(path: Path, row: dict) -> None:
    with path.open("a") as f:
        f.write(json.dumps(row) + "\n")


def whole_grid(grid: Grid) -> Grid:
    return base.copy_grid(grid)


def region_sort_key_top_left(region: dict) -> tuple:
    r0, c0 = region["origin"]
    h, w = base.shape(region["grid"])
    return (r0, c0, h * w, h, w, region["label"])


def region_sort_key_bottom_right(region: dict) -> tuple:
    r0, c0 = region["origin"]
    h, w = base.shape(region["grid"])
    return (-(r0 + h), -(c0 + w), -(h * w), -h, -w, region["label"])


def split_intervals(size: int, separators: list[int]) -> list[tuple[int, int]]:
    boundaries = [-1] + sorted(set(separators)) + [size]
    intervals = []
    for idx in range(len(boundaries) - 1):
        start = boundaries[idx] + 1
        end = boundaries[idx + 1]
        if start < end:
            intervals.append((start, end))
    return intervals


def full_separator_rows(grid: Grid, color: int) -> list[int]:
    return [r for r, row in enumerate(grid) if all(cell == color for cell in row)]


def full_separator_cols(grid: Grid, color: int) -> list[int]:
    h, w = base.shape(grid)
    return [c for c in range(w) if all(grid[r][c] == color for r in range(h))]


def enumerate_regions(grid: Grid) -> list[dict]:
    h, w = base.shape(grid)
    regions = [
        {
            "label": "whole",
            "grid": base.copy_grid(grid),
            "origin": (0, 0),
            "separator_color": None,
            "mode": "whole",
        }
    ]
    seen = {(0, 0, h, w, "whole")}
    for color in base.all_colors(grid):
        row_seps = full_separator_rows(grid, color)
        col_seps = full_separator_cols(grid, color)
        if not row_seps and not col_seps:
            continue
        row_ranges = split_intervals(h, row_seps) if row_seps else [(0, h)]
        col_ranges = split_intervals(w, col_seps) if col_seps else [(0, w)]
        mode = []
        if row_seps:
            mode.append("rows")
        if col_seps:
            mode.append("cols")
        mode_name = "_".join(mode)
        for ridx, (r0, r1) in enumerate(row_ranges):
            for cidx, (c0, c1) in enumerate(col_ranges):
                region_grid = [row[c0:c1] for row in grid[r0:r1]]
                key = (r0, c0, r1 - r0, c1 - c0, mode_name, color)
                if not region_grid or key in seen:
                    continue
                seen.add(key)
                regions.append(
                    {
                        "label": f"{mode_name}:sep{color}:r{ridx}:c{cidx}",
                        "grid": region_grid,
                        "origin": (r0, c0),
                        "separator_color": color,
                        "mode": mode_name,
                    }
                )
    return regions


def select_region(grid: Grid, selector_name: str) -> Grid | None:
    regions = enumerate_regions(grid)
    if selector_name == "whole":
        return base.copy_grid(grid)
    if len(regions) <= 1:
        return None

    if selector_name == "largest_area":
        picked = sorted(regions[1:], key=lambda region: (-base.shape(region["grid"])[0] * base.shape(region["grid"])[1], region_sort_key_top_left(region)))[0]
    elif selector_name == "smallest_area":
        picked = sorted(regions[1:], key=lambda region: (base.shape(region["grid"])[0] * base.shape(region["grid"])[1], region_sort_key_top_left(region)))[0]
    elif selector_name == "top_left":
        picked = sorted(regions[1:], key=region_sort_key_top_left)[0]
    elif selector_name == "top_right":
        picked = sorted(regions[1:], key=lambda region: (region["origin"][0], -region["origin"][1], region["label"]))[0]
    elif selector_name == "bottom_left":
        picked = sorted(regions[1:], key=lambda region: (-region["origin"][0], region["origin"][1], region["label"]))[0]
    elif selector_name == "bottom_right":
        picked = sorted(regions[1:], key=region_sort_key_bottom_right)[0]
    elif selector_name == "first":
        picked = sorted(regions[1:], key=region_sort_key_top_left)[0]
    elif selector_name == "last":
        picked = sorted(regions[1:], key=region_sort_key_bottom_right)[0]
    else:
        return None
    return base.copy_grid(picked["grid"])


def anchor_point(grid: Grid, anchor_name: str) -> tuple[float, float]:
    h, w = base.shape(grid)
    points = {
        "top_left": (0.0, 0.0),
        "top_right": (0.0, float(max(0, w - 1))),
        "bottom_left": (float(max(0, h - 1)), 0.0),
        "bottom_right": (float(max(0, h - 1)), float(max(0, w - 1))),
        "center": (float(max(0, h - 1)) / 2.0, float(max(0, w - 1)) / 2.0),
    }
    return points[anchor_name]


def foreground_objects(grid: Grid, bg: int | None = None) -> list[dict[str, object]]:
    if bg is None:
        bg = base.background_color(grid)
    h, w = base.shape(grid)
    seen = [[False] * w for _ in range(h)]
    objects = []
    for r in range(h):
        for c in range(w):
            if seen[r][c] or grid[r][c] == bg:
                continue
            stack = [(r, c)]
            seen[r][c] = True
            cells: list[tuple[int, int]] = []
            colors = set()
            while stack:
                cr, cc = stack.pop()
                cells.append((cr, cc))
                colors.add(grid[cr][cc])
                for nr, nc in ((cr - 1, cc), (cr + 1, cc), (cr, cc - 1), (cr, cc + 1)):
                    if 0 <= nr < h and 0 <= nc < w and not seen[nr][nc] and grid[nr][nc] != bg:
                        seen[nr][nc] = True
                        stack.append((nr, nc))
            rows = [row for row, _ in cells]
            cols = [col for _, col in cells]
            objects.append(
                {
                    "color": min(colors),
                    "colors": tuple(sorted(colors)),
                    "size": len(cells),
                    "cells": cells,
                    "bbox": (min(rows), max(rows), min(cols), max(cols)),
                }
            )
    return objects


def object_components(grid: Grid, component_kind: str) -> list[dict[str, object]]:
    if component_kind == "color":
        return base.connected_components(grid)
    if component_kind == "foreground":
        return foreground_objects(grid)
    raise ValueError(f"Unsupported component kind: {component_kind}")


def selectors_for_component_kind(component_kind: str) -> list[str]:
    shared = [
        "largest",
        "smallest",
        "topmost",
        "leftmost",
        "rightmost",
        "bottommost",
        "top_left",
        "bottom_right",
        "nearest_to_top_left",
        "nearest_to_top_right",
        "nearest_to_bottom_left",
        "nearest_to_bottom_right",
        "nearest_to_center",
        "farthest_from_top_left",
        "farthest_from_bottom_right",
    ]
    if component_kind == "color":
        return shared + ["least_freq_color", "most_freq_color"]
    return shared


def select_component_extended(
    grid: Grid,
    selector_name: str,
    component_kind: str = "color",
) -> dict[str, object] | None:
    builtin = {"largest", "smallest", "topmost", "leftmost", "rightmost", "bottommost", "top_left", "bottom_right"}
    if selector_name in builtin and component_kind == "color":
        return base.select_component(grid, selector_name)

    comps = object_components(grid, component_kind)
    if not comps:
        return None

    def key_top_left(comp: dict[str, object]) -> tuple:
        r0, r1, c0, c1 = comp["bbox"]  # type: ignore[index]
        return (r0, c0, r1, c1, -comp["size"], comp["color"])

    def key_bottom_right(comp: dict[str, object]) -> tuple:
        r0, r1, c0, c1 = comp["bbox"]  # type: ignore[index]
        return (-r1, -c1, -r0, -c0, -comp["size"], comp["color"])

    if selector_name in builtin:
        orders = {
            "largest": sorted(comps, key=lambda comp: (-comp["size"], key_top_left(comp))),
            "smallest": sorted(comps, key=lambda comp: (comp["size"], key_top_left(comp))),
            "topmost": sorted(comps, key=key_top_left),
            "leftmost": sorted(comps, key=lambda comp: (comp["bbox"][2], comp["bbox"][0], -comp["size"], comp["color"])),  # type: ignore[index]
            "rightmost": sorted(comps, key=lambda comp: (-comp["bbox"][3], comp["bbox"][0], -comp["size"], comp["color"])),  # type: ignore[index]
            "bottommost": sorted(comps, key=lambda comp: (-comp["bbox"][1], comp["bbox"][2], -comp["size"], comp["color"])),  # type: ignore[index]
            "top_left": sorted(comps, key=key_top_left),
            "bottom_right": sorted(comps, key=key_bottom_right),
        }
        return orders[selector_name][0]

    if selector_name == "least_freq_color" and component_kind == "color":
        colors = base.non_bg_colors_by_frequency(grid)
        if not colors:
            return None
        target_color = colors[0]
        candidates = [comp for comp in comps if comp["color"] == target_color]
        return sorted(candidates, key=lambda comp: (-comp["size"], comp["bbox"]))[0]

    if selector_name == "most_freq_color" and component_kind == "color":
        colors = base.non_bg_colors_by_frequency(grid)
        if not colors:
            return None
        target_color = colors[-1]
        candidates = [comp for comp in comps if comp["color"] == target_color]
        return sorted(candidates, key=lambda comp: (-comp["size"], comp["bbox"]))[0]

    if selector_name.startswith("nearest_") or selector_name.startswith("farthest_"):
        mode, _, anchor = selector_name.partition("_")
        anchor_name = anchor.removeprefix("to_").removeprefix("from_")
        ar, ac = anchor_point(grid, anchor_name)

        def dist(comp: dict[str, object]) -> tuple[float, tuple]:
            r0, r1, c0, c1 = comp["bbox"]  # type: ignore[index]
            cr = (r0 + r1) / 2.0
            cc = (c0 + c1) / 2.0
            squared = (cr - ar) ** 2 + (cc - ac) ** 2
            return squared, (r0, c0, -comp["size"], comp["color"])

        if selector_name.startswith("nearest_"):
            return min(comps, key=dist)
        return max(comps, key=dist)

    return None


def select_source_grid(grid: Grid, source_name: str) -> Grid | None:
    if source_name == "whole":
        return base.copy_grid(grid)
    if source_name.startswith("region:"):
        return select_region(grid, source_name.split(":", 1)[1])
    return None


def apply_transform(grid: Grid | None, transform_name: str) -> Grid | None:
    if grid is None:
        return None
    return tags.TRANSFORMS[transform_name](grid)


def extract_selected_component(
    grid: Grid,
    source_name: str,
    component_kind: str,
    component_selector: str,
    fill_mode: str,
    transform_name: str,
) -> Grid | None:
    source = select_source_grid(grid, source_name)
    if source is None:
        return None
    component = select_component_extended(source, component_selector, component_kind)
    if component is None:
        return None
    cropped = base.component_to_grid(source, component, fill_mode)
    return apply_transform(cropped, transform_name)


def component_relative_cells(component: dict[str, object]) -> tuple[tuple[int, int], ...]:
    r0, _, c0, _ = component["bbox"]  # type: ignore[index]
    cells = sorted((r - r0, c - c0) for r, c in component["cells"])  # type: ignore[index]
    return tuple(cells)


def object_color_mapping(
    input_grid: Grid,
    input_component: dict[str, object],
    output_grid: Grid,
    output_component: dict[str, object],
) -> dict[int, int] | None:
    in_r0, _, in_c0, _ = input_component["bbox"]  # type: ignore[index]
    out_r0, _, out_c0, _ = output_component["bbox"]  # type: ignore[index]
    mapping: dict[int, int] = {}
    for r, c in input_component["cells"]:  # type: ignore[index]
        src = input_grid[r][c]
        dst = output_grid[out_r0 + (r - in_r0)][out_c0 + (c - in_c0)]
        if src in mapping and mapping[src] != dst:
            return None
        mapping[src] = dst
    return mapping


def component_anchor_cell(component: dict[str, object], anchor_name: str) -> tuple[int, int]:
    r0, r1, c0, c1 = component["bbox"]  # type: ignore[index]
    points = {
        "top_left": (r0, c0),
        "top_right": (r0, c1),
        "bottom_left": (r1, c0),
        "bottom_right": (r1, c1),
        "center": ((r0 + r1) // 2, (c0 + c1) // 2),
    }
    return points[anchor_name]


def grid_anchor_offset(height: int, width: int, anchor_name: str) -> tuple[int, int]:
    points = {
        "top_left": (0, 0),
        "top_right": (0, max(0, width - 1)),
        "bottom_left": (max(0, height - 1), 0),
        "bottom_right": (max(0, height - 1), max(0, width - 1)),
        "center": (max(0, height - 1) // 2, max(0, width - 1) // 2),
    }
    return points[anchor_name]


def relational_selectors(component_kind: str) -> list[str]:
    shared = [
        "largest",
        "smallest",
        "topmost",
        "bottommost",
        "leftmost",
        "rightmost",
        "top_left",
        "bottom_right",
        "nearest_to_center",
    ]
    if component_kind == "color":
        return shared + ["least_freq_color", "most_freq_color"]
    return shared


def paint_relation_selectors(component_kind: str) -> list[str]:
    shared = ["largest", "smallest", "top_left", "bottom_right", "nearest_to_center"]
    if component_kind == "color":
        return shared + ["least_freq_color", "most_freq_color"]
    return shared


def group_filter_names(component_kind: str) -> list[str]:
    shared = [
        "all",
        "largest_size_group",
        "smallest_size_group",
        "top_band",
        "bottom_band",
        "left_band",
        "right_band",
        "touching_border",
        "interior_only",
        "nearest_center_group",
    ]
    if component_kind == "color":
        return shared + ["least_freq_color_group", "most_freq_color_group"]
    return shared


def select_component_group(grid: Grid, component_kind: str, filter_name: str) -> list[dict[str, object]]:
    comps = object_components(grid, component_kind)
    if not comps:
        return []

    h, w = base.shape(grid)
    if filter_name == "all":
        return comps
    if filter_name == "largest_size_group":
        target = max(comp["size"] for comp in comps)
        return [comp for comp in comps if comp["size"] == target]
    if filter_name == "smallest_size_group":
        target = min(comp["size"] for comp in comps)
        return [comp for comp in comps if comp["size"] == target]
    if filter_name == "top_band":
        target = min(comp["bbox"][0] for comp in comps)  # type: ignore[index]
        return [comp for comp in comps if comp["bbox"][0] == target]  # type: ignore[index]
    if filter_name == "bottom_band":
        target = max(comp["bbox"][1] for comp in comps)  # type: ignore[index]
        return [comp for comp in comps if comp["bbox"][1] == target]  # type: ignore[index]
    if filter_name == "left_band":
        target = min(comp["bbox"][2] for comp in comps)  # type: ignore[index]
        return [comp for comp in comps if comp["bbox"][2] == target]  # type: ignore[index]
    if filter_name == "right_band":
        target = max(comp["bbox"][3] for comp in comps)  # type: ignore[index]
        return [comp for comp in comps if comp["bbox"][3] == target]  # type: ignore[index]
    if filter_name == "touching_border":
        return [
            comp
            for comp in comps
            if comp["bbox"][0] == 0 or comp["bbox"][2] == 0 or comp["bbox"][1] == h - 1 or comp["bbox"][3] == w - 1  # type: ignore[index]
        ]
    if filter_name == "interior_only":
        return [
            comp
            for comp in comps
            if comp["bbox"][0] > 0 and comp["bbox"][2] > 0 and comp["bbox"][1] < h - 1 and comp["bbox"][3] < w - 1  # type: ignore[index]
        ]
    if filter_name == "nearest_center_group":
        center_r, center_c = anchor_point(grid, "center")
        best = min(
            ((component_anchor_cell(comp, "center")[0] - center_r) ** 2 + (component_anchor_cell(comp, "center")[1] - center_c) ** 2)
            for comp in comps
        )
        return [
            comp
            for comp in comps
            if ((component_anchor_cell(comp, "center")[0] - center_r) ** 2 + (component_anchor_cell(comp, "center")[1] - center_c) ** 2) == best
        ]
    if filter_name == "least_freq_color_group" and component_kind == "color":
        colors = base.non_bg_colors_by_frequency(grid)
        if not colors:
            return []
        target = colors[0]
        return [comp for comp in comps if comp["color"] == target]
    if filter_name == "most_freq_color_group" and component_kind == "color":
        colors = base.non_bg_colors_by_frequency(grid)
        if not colors:
            return []
        target = colors[-1]
        return [comp for comp in comps if comp["color"] == target]
    return []


def crop_union_of_selected_components(
    grid: Grid,
    component_kind: str,
    first_selector: str,
    second_selector: str,
    mask_mode: str,
    transform_name: str,
) -> Grid | None:
    first = select_component_extended(grid, first_selector, component_kind)
    second = select_component_extended(grid, second_selector, component_kind)
    if first is None or second is None:
        return None
    r0 = min(first["bbox"][0], second["bbox"][0])  # type: ignore[index]
    r1 = max(first["bbox"][1], second["bbox"][1])  # type: ignore[index]
    c0 = min(first["bbox"][2], second["bbox"][2])  # type: ignore[index]
    c1 = max(first["bbox"][3], second["bbox"][3])  # type: ignore[index]
    cropped = base.crop_box(grid, (r0, r1, c0, c1))
    if mask_mode == "pair_only":
        keep = set(first["cells"]) | set(second["cells"])  # type: ignore[arg-type]
        fill = base.background_color(grid)
        cropped = [
            [
                grid[r0 + rr][c0 + cc] if (r0 + rr, c0 + cc) in keep else fill
                for cc in range(c1 - c0 + 1)
            ]
            for rr in range(r1 - r0 + 1)
        ]
    return apply_transform(cropped, transform_name)


def render_component_group(grid: Grid, components: list[dict[str, object]], canvas_mode: str) -> Grid | None:
    if not components:
        return None
    bg = base.background_color(grid)
    if canvas_mode == "blank_same_shape":
        out = base.zero_grid_like(grid)
        for comp in components:
            for r, c in comp["cells"]:  # type: ignore[index]
                out[r][c] = grid[r][c]
        return out
    if canvas_mode == "input_remove_group":
        out = base.copy_grid(grid)
        for comp in components:
            for r, c in comp["cells"]:  # type: ignore[index]
                out[r][c] = bg
        return out
    return None


def crop_union_of_component_group(
    grid: Grid,
    component_kind: str,
    filter_name: str,
    mask_mode: str,
    transform_name: str,
) -> Grid | None:
    comps = select_component_group(grid, component_kind, filter_name)
    if not comps:
        return None
    r0 = min(comp["bbox"][0] for comp in comps)  # type: ignore[index]
    r1 = max(comp["bbox"][1] for comp in comps)  # type: ignore[index]
    c0 = min(comp["bbox"][2] for comp in comps)  # type: ignore[index]
    c1 = max(comp["bbox"][3] for comp in comps)  # type: ignore[index]
    if mask_mode == "full":
        cropped = base.crop_box(grid, (r0, r1, c0, c1))
    else:
        keep = set()
        for comp in comps:
            keep.update(comp["cells"])  # type: ignore[arg-type]
        fill = base.background_color(grid)
        cropped = [
            [
                grid[r0 + rr][c0 + cc] if (r0 + rr, c0 + cc) in keep else fill
                for cc in range(c1 - c0 + 1)
            ]
            for rr in range(r1 - r0 + 1)
        ]
    return apply_transform(cropped, transform_name)


def paint_selected_object_relative(
    grid: Grid,
    component_kind: str,
    source_selector: str,
    anchor_selector: str,
    transform_name: str,
    canvas_mode: str,
    source_anchor: str,
    target_anchor: str,
    color_mode: str,
    fixed_mapping: dict[int, int] | None,
) -> Grid | None:
    source = select_component_extended(grid, source_selector, component_kind)
    anchor = select_component_extended(grid, anchor_selector, component_kind)
    if source is None or anchor is None:
        return None

    source_grid = base.component_to_grid(grid, source, "original_bg")
    source_grid = apply_transform(source_grid, transform_name)
    if source_grid is None:
        return None

    bg = base.background_color(grid)
    transparent = bg
    if canvas_mode == "blank":
        canvas = base.zero_grid_like(grid)
    elif canvas_mode == "input":
        canvas = base.copy_grid(grid)
    elif canvas_mode == "input_without_source":
        canvas = base.copy_grid(grid)
        for r, c in source["cells"]:  # type: ignore[index]
            canvas[r][c] = bg
    else:
        return None

    src_h, src_w = base.shape(source_grid)
    src_anchor_r, src_anchor_c = grid_anchor_offset(src_h, src_w, source_anchor)
    tgt_anchor_r, tgt_anchor_c = component_anchor_cell(anchor, target_anchor)
    top = tgt_anchor_r - src_anchor_r
    left = tgt_anchor_c - src_anchor_c

    if color_mode == "identity":
        mapping = {color: color for color in base.all_colors(source_grid)}
    elif color_mode == "anchor_primary":
        mapping = {
            color: (anchor["color"] if color != transparent else transparent)  # type: ignore[index]
            for color in base.all_colors(source_grid)
        }
    elif color_mode == "fixed" and fixed_mapping is not None:
        mapping = dict(fixed_mapping)
        mapping.setdefault(transparent, transparent)
    else:
        return None

    recolored = []
    for row in source_grid:
        recolored_row = []
        for cell in row:
            if cell not in mapping:
                return None
            recolored_row.append(mapping[cell])
        recolored.append(recolored_row)
    return overlay_component(canvas, recolored, top, left, transparent_color=transparent)


def placement_mapping_for_rule(
    input_grid: Grid,
    output_grid: Grid,
    component_kind: str,
    source_selector: str,
    anchor_selector: str,
    transform_name: str,
    canvas_mode: str,
    source_anchor: str,
    target_anchor: str,
) -> dict[int, int] | None:
    source = select_component_extended(input_grid, source_selector, component_kind)
    anchor = select_component_extended(input_grid, anchor_selector, component_kind)
    if source is None or anchor is None:
        return None

    source_grid = base.component_to_grid(input_grid, source, "original_bg")
    source_grid = apply_transform(source_grid, transform_name)
    if source_grid is None:
        return None

    bg = base.background_color(input_grid)
    src_h, src_w = base.shape(source_grid)
    src_anchor_r, src_anchor_c = grid_anchor_offset(src_h, src_w, source_anchor)
    tgt_anchor_r, tgt_anchor_c = component_anchor_cell(anchor, target_anchor)
    top = tgt_anchor_r - src_anchor_r
    left = tgt_anchor_c - src_anchor_c
    if top < 0 or left < 0 or top + src_h > len(input_grid) or left + src_w > len(input_grid[0]):
        return None

    mapping: dict[int, int] = {bg: bg}
    for r in range(src_h):
        for c in range(src_w):
            src = source_grid[r][c]
            if src == bg:
                continue
            dst = output_grid[top + r][left + c]
            if src in mapping and mapping[src] != dst:
                return None
            mapping[src] = dst

    predicted = paint_selected_object_relative(
        input_grid,
        component_kind,
        source_selector,
        anchor_selector,
        transform_name,
        canvas_mode,
        source_anchor,
        target_anchor,
        "fixed",
        mapping,
    )
    if predicted != output_grid:
        return None
    return mapping


def move_or_copy_selected_object(
    grid: Grid,
    component_kind: str,
    component_selector: str,
    delta: tuple[int, int],
    keep_original: bool,
    color_mapping: dict[int, int],
) -> Grid | None:
    component = select_component_extended(grid, component_selector, component_kind)
    if component is None:
        return None

    dr, dc = delta
    out = base.copy_grid(grid)
    bg = base.background_color(grid)
    if not keep_original:
        for r, c in component["cells"]:  # type: ignore[index]
            out[r][c] = bg

    for r, c in component["cells"]:  # type: ignore[index]
        nr = r + dr
        nc = c + dc
        if nr < 0 or nc < 0 or nr >= len(out) or nc >= len(out[0]):
            return None
        value = grid[r][c]
        if value not in color_mapping:
            return None
        out[nr][nc] = color_mapping[value]
    return out


def infer_move_copy_rules(train: list[Pair]) -> list[RuleCandidate]:
    if not all(base.shape(pair["input"]) == base.shape(pair["output"]) for pair in train):
        return []

    rules = []
    for component_kind in ("color", "foreground"):
        for component_selector in selectors_for_component_kind(component_kind):
            for keep_original in (False, True):
                shared_candidates: set[tuple[tuple[int, int], tuple[tuple[int, int], ...]]] | None = None
                for pair in train:
                    selected = select_component_extended(pair["input"], component_selector, component_kind)
                    if selected is None:
                        shared_candidates = set()
                        break
                    selected_shape = component_relative_cells(selected)
                    local: set[tuple[tuple[int, int], tuple[tuple[int, int], ...]]] = set()
                    for out_comp in object_components(pair["output"], component_kind):
                        if component_relative_cells(out_comp) != selected_shape:
                            continue
                        delta = (
                            out_comp["bbox"][0] - selected["bbox"][0],  # type: ignore[index]
                            out_comp["bbox"][2] - selected["bbox"][2],  # type: ignore[index]
                        )
                        mapping = object_color_mapping(pair["input"], selected, pair["output"], out_comp)
                        if mapping is None:
                            continue
                        predicted = move_or_copy_selected_object(
                            pair["input"],
                            component_kind,
                            component_selector,
                            delta,
                            keep_original,
                            mapping,
                        )
                        if predicted == pair["output"]:
                            local.add((delta, tuple(sorted(mapping.items()))))
                    shared_candidates = local if shared_candidates is None else shared_candidates & local
                    if not shared_candidates:
                        break

                if not shared_candidates:
                    continue

                for delta, mapping_items in sorted(shared_candidates):
                    mapping_dict = dict(mapping_items)
                    rules.append(
                        RuleCandidate(
                            name=(
                                f"move_copy:{component_kind}:{component_selector}:"
                                f"{'copy' if keep_original else 'move'}:{delta[0]}:{delta[1]}:{mapping_items}"
                            ),
                            family="object_move_copy",
                            priority=130,
                            apply=lambda grid, ck=component_kind, cs=component_selector, d=delta, ko=keep_original, cmap=mapping_dict: move_or_copy_selected_object(
                                grid,
                                ck,
                                cs,
                                d,
                                ko,
                                cmap,
                            ),
                            metadata={
                                "component_kind": component_kind,
                                "component_selector": component_selector,
                                "mode": "copy" if keep_original else "move",
                                "delta": list(delta),
                                "color_mapping": mapping_dict,
                            },
                        )
                    )
    return rules


def infer_relation_crop_rules() -> list[RuleCandidate]:
    rules = []
    transforms = ["identity", "rot180", "flip_h", "flip_v", "transpose"]
    for component_kind in ("color", "foreground"):
        selectors = relational_selectors(component_kind)
        for first_selector in selectors:
            for second_selector in selectors:
                for mask_mode in ("full", "pair_only"):
                    for transform_name in transforms:
                        rules.append(
                            RuleCandidate(
                                name=f"relation_crop:{component_kind}:{first_selector}:{second_selector}:{mask_mode}:{transform_name}",
                                family="relation_crop",
                                priority=105,
                                apply=lambda grid, ck=component_kind, fs=first_selector, ss=second_selector, mm=mask_mode, tn=transform_name: crop_union_of_selected_components(
                                    grid,
                                    ck,
                                    fs,
                                    ss,
                                    mm,
                                    tn,
                                ),
                                metadata={
                                    "component_kind": component_kind,
                                    "first_selector": first_selector,
                                    "second_selector": second_selector,
                                    "mask_mode": mask_mode,
                                    "transform": transform_name,
                                },
                            )
                        )
    return rules


def infer_group_rules() -> list[RuleCandidate]:
    rules = []
    transforms = ["identity", "rot180", "flip_h", "flip_v", "transpose"]
    for component_kind in ("color", "foreground"):
        for filter_name in group_filter_names(component_kind):
            for canvas_mode in ("blank_same_shape", "input_remove_group"):
                rules.append(
                    RuleCandidate(
                        name=f"group_render:{component_kind}:{filter_name}:{canvas_mode}",
                        family="group_render",
                        priority=110,
                        apply=lambda grid, ck=component_kind, fn=filter_name, cm=canvas_mode: render_component_group(
                            grid,
                            select_component_group(grid, ck, fn),
                            cm,
                        ),
                        metadata={
                            "component_kind": component_kind,
                            "filter_name": filter_name,
                            "canvas_mode": canvas_mode,
                        },
                    )
                )
            for mask_mode in ("full", "group_only"):
                for transform_name in transforms:
                    rules.append(
                        RuleCandidate(
                            name=f"group_crop:{component_kind}:{filter_name}:{mask_mode}:{transform_name}",
                            family="group_crop",
                            priority=111,
                            apply=lambda grid, ck=component_kind, fn=filter_name, mm=mask_mode, tn=transform_name: crop_union_of_component_group(
                                grid,
                                ck,
                                fn,
                                mm,
                                tn,
                            ),
                            metadata={
                                "component_kind": component_kind,
                                "filter_name": filter_name,
                                "mask_mode": mask_mode,
                                "transform": transform_name,
                            },
                        )
                    )
    return rules


def infer_relative_paint_rules(train: list[Pair]) -> list[RuleCandidate]:
    if not all(base.shape(pair["input"]) == base.shape(pair["output"]) for pair in train):
        return []

    rules = []
    transforms = ["identity", "rot180", "flip_h", "flip_v"]
    anchors = ["top_left", "center", "bottom_right"]
    canvas_modes = ["blank", "input_without_source"]

    for component_kind in ("color", "foreground"):
        selectors = paint_relation_selectors(component_kind)
        for source_selector in selectors:
            for anchor_selector in selectors:
                for transform_name in transforms:
                    for source_anchor in anchors:
                        for target_anchor in anchors:
                            for canvas_mode in canvas_modes:
                                shared_fixed: set[tuple[tuple[int, int], ...]] | None = None
                                anchor_primary_ok = True
                                identity_ok = True
                                for pair in train:
                                    source = select_component_extended(pair["input"], source_selector, component_kind)
                                    anchor = select_component_extended(pair["input"], anchor_selector, component_kind)
                                    if source is None or anchor is None:
                                        shared_fixed = set()
                                        anchor_primary_ok = False
                                        identity_ok = False
                                        break

                                    mapping = placement_mapping_for_rule(
                                        pair["input"],
                                        pair["output"],
                                        component_kind,
                                        source_selector,
                                        anchor_selector,
                                        transform_name,
                                        canvas_mode,
                                        source_anchor,
                                        target_anchor,
                                    )
                                    if mapping is None:
                                        shared_fixed = set()
                                        anchor_primary_ok = False
                                        identity_ok = False
                                        break

                                    predicted_identity = paint_selected_object_relative(
                                        pair["input"],
                                        component_kind,
                                        source_selector,
                                        anchor_selector,
                                        transform_name,
                                        canvas_mode,
                                        source_anchor,
                                        target_anchor,
                                        "identity",
                                        None,
                                    )
                                    identity_ok = identity_ok and (predicted_identity == pair["output"])

                                    predicted_anchor_primary = paint_selected_object_relative(
                                        pair["input"],
                                        component_kind,
                                        source_selector,
                                        anchor_selector,
                                        transform_name,
                                        canvas_mode,
                                        source_anchor,
                                        target_anchor,
                                        "anchor_primary",
                                        None,
                                    )
                                    anchor_primary_ok = anchor_primary_ok and (predicted_anchor_primary == pair["output"])

                                    mapping_items = tuple(sorted(mapping.items()))
                                    local_fixed = {mapping_items}
                                    shared_fixed = local_fixed if shared_fixed is None else shared_fixed & local_fixed

                                if identity_ok:
                                    rules.append(
                                        RuleCandidate(
                                            name=(
                                                f"relative_paint:{component_kind}:{source_selector}:{anchor_selector}:"
                                                f"{transform_name}:{canvas_mode}:{source_anchor}:{target_anchor}:identity"
                                            ),
                                            family="relative_paint",
                                            priority=135,
                                            apply=lambda grid, ck=component_kind, ss=source_selector, an=anchor_selector, tn=transform_name, cm=canvas_mode, sa=source_anchor, ta=target_anchor: paint_selected_object_relative(
                                                grid,
                                                ck,
                                                ss,
                                                an,
                                                tn,
                                                cm,
                                                sa,
                                                ta,
                                                "identity",
                                                None,
                                            ),
                                            metadata={
                                                "component_kind": component_kind,
                                                "source_selector": source_selector,
                                                "anchor_selector": anchor_selector,
                                                "transform": transform_name,
                                                "canvas_mode": canvas_mode,
                                                "source_anchor": source_anchor,
                                                "target_anchor": target_anchor,
                                                "color_mode": "identity",
                                            },
                                        )
                                    )

                                if anchor_primary_ok:
                                    rules.append(
                                        RuleCandidate(
                                            name=(
                                                f"relative_paint:{component_kind}:{source_selector}:{anchor_selector}:"
                                                f"{transform_name}:{canvas_mode}:{source_anchor}:{target_anchor}:anchor_primary"
                                            ),
                                            family="relative_paint",
                                            priority=136,
                                            apply=lambda grid, ck=component_kind, ss=source_selector, an=anchor_selector, tn=transform_name, cm=canvas_mode, sa=source_anchor, ta=target_anchor: paint_selected_object_relative(
                                                grid,
                                                ck,
                                                ss,
                                                an,
                                                tn,
                                                cm,
                                                sa,
                                                ta,
                                                "anchor_primary",
                                                None,
                                            ),
                                            metadata={
                                                "component_kind": component_kind,
                                                "source_selector": source_selector,
                                                "anchor_selector": anchor_selector,
                                                "transform": transform_name,
                                                "canvas_mode": canvas_mode,
                                                "source_anchor": source_anchor,
                                                "target_anchor": target_anchor,
                                                "color_mode": "anchor_primary",
                                            },
                                        )
                                    )

                                if shared_fixed:
                                    for mapping_items in sorted(shared_fixed):
                                        mapping_dict = dict(mapping_items)
                                        rules.append(
                                            RuleCandidate(
                                                name=(
                                                    f"relative_paint:{component_kind}:{source_selector}:{anchor_selector}:"
                                                    f"{transform_name}:{canvas_mode}:{source_anchor}:{target_anchor}:fixed:{mapping_items}"
                                                ),
                                                family="relative_paint",
                                                priority=137,
                                                apply=lambda grid, ck=component_kind, ss=source_selector, an=anchor_selector, tn=transform_name, cm=canvas_mode, sa=source_anchor, ta=target_anchor, fmap=mapping_dict: paint_selected_object_relative(
                                                    grid,
                                                    ck,
                                                    ss,
                                                    an,
                                                    tn,
                                                    cm,
                                                    sa,
                                                    ta,
                                                    "fixed",
                                                    fmap,
                                                ),
                                                metadata={
                                                    "component_kind": component_kind,
                                                    "source_selector": source_selector,
                                                    "anchor_selector": anchor_selector,
                                                    "transform": transform_name,
                                                    "canvas_mode": canvas_mode,
                                                    "source_anchor": source_anchor,
                                                    "target_anchor": target_anchor,
                                                    "color_mode": "fixed",
                                                    "fixed_mapping": mapping_dict,
                                                },
                                            )
                                        )
    return rules


def consistent_output_shape_mode(train: list[Pair]) -> tuple[str, tuple[int, int] | None] | None:
    input_shape_matches = all(base.shape(pair["input"]) == base.shape(pair["output"]) for pair in train)
    if input_shape_matches:
        return "input_shape", None
    out_shapes = {base.shape(pair["output"]) for pair in train}
    if len(out_shapes) == 1:
        return "fixed_shape", next(iter(out_shapes))
    return None


def anchor_offsets(canvas_h: int, canvas_w: int, obj_h: int, obj_w: int) -> dict[str, tuple[int, int]]:
    return {
        "top_left": (0, 0),
        "top_right": (0, canvas_w - obj_w),
        "bottom_left": (canvas_h - obj_h, 0),
        "bottom_right": (canvas_h - obj_h, canvas_w - obj_w),
        "center": ((canvas_h - obj_h) // 2, (canvas_w - obj_w) // 2),
    }


def fill_color_from_mode(grid: Grid, mode: str, constant: int | None = None) -> int:
    if mode == "zero":
        return 0
    if mode == "input_bg":
        return base.background_color(grid)
    if mode == "constant" and constant is not None:
        return constant
    raise ValueError(f"Unsupported fill mode: {mode}")


def overlay_component(
    canvas: Grid,
    component_grid: Grid,
    top: int,
    left: int,
    transparent_color: int | None = None,
) -> Grid | None:
    out = base.copy_grid(canvas)
    canvas_h, canvas_w = base.shape(canvas)
    obj_h, obj_w = base.shape(component_grid)
    if top < 0 or left < 0 or top + obj_h > canvas_h or left + obj_w > canvas_w:
        return None
    for r in range(obj_h):
        for c in range(obj_w):
            value = component_grid[r][c]
            if transparent_color is not None and value == transparent_color:
                continue
            out[top + r][left + c] = value
    return out


def build_canvas_program(
    grid: Grid,
    source_name: str,
    component_kind: str,
    component_selector: str,
    fill_mode: str,
    transform_name: str,
    canvas_mode: str,
    canvas_fill_mode: str,
    anchor_name: str,
    fixed_shape: tuple[int, int] | None,
    constant_fill: int | None,
) -> Grid | None:
    source = select_source_grid(grid, source_name)
    if source is None:
        return None
    component = select_component_extended(source, component_selector, component_kind)
    if component is None:
        return None
    object_grid = base.component_to_grid(source, component, fill_mode)
    object_grid = apply_transform(object_grid, transform_name)
    if object_grid is None:
        return None

    if canvas_mode == "blank":
        if fixed_shape is None:
            canvas_h, canvas_w = base.shape(grid)
        else:
            canvas_h, canvas_w = fixed_shape
        fill = fill_color_from_mode(grid, canvas_fill_mode, constant_fill)
        canvas = base.zero_grid(canvas_h, canvas_w, fill)
        transparent = fill if fill_mode == "original_bg" else 0
    elif canvas_mode == "input_without_selected":
        canvas = base.copy_grid(grid)
        bg = base.background_color(grid)
        for r, c in component["cells"]:  # type: ignore[index]
            canvas[r][c] = bg
        transparent = base.background_color(source) if fill_mode == "original_bg" else 0
    else:
        return None

    obj_h, obj_w = base.shape(object_grid)
    canvas_h, canvas_w = base.shape(canvas)
    top, left = anchor_offsets(canvas_h, canvas_w, obj_h, obj_w)[anchor_name]
    return overlay_component(canvas, object_grid, top, left, transparent_color=transparent)


def infer_region_extract_rules() -> list[RuleCandidate]:
    rules = []
    region_selectors = ["whole", "largest_area", "smallest_area", "top_left", "top_right", "bottom_left", "bottom_right", "first", "last"]
    transforms = ["identity", "rot180", "flip_h", "flip_v", "transpose"]
    for region_selector in region_selectors:
        for transform_name in transforms:
            rules.append(
                RuleCandidate(
                    name=f"region_extract:{region_selector}:{transform_name}",
                    family="region_extract",
                    priority=90,
                    apply=lambda grid, rs=region_selector, tn=transform_name: apply_transform(select_source_grid(grid, "whole" if rs == "whole" else f"region:{rs}"), tn),
                    metadata={"region_selector": region_selector, "transform": transform_name},
                )
            )
    return rules


def infer_component_program_rules() -> list[RuleCandidate]:
    rules = []
    source_names = ["whole", "region:largest_area", "region:top_left", "region:top_right", "region:bottom_left", "region:bottom_right"]
    transforms = ["identity", "rot180", "flip_h", "flip_v", "transpose"]
    for source_name in source_names:
        for component_kind in ("color", "foreground"):
            for component_selector in selectors_for_component_kind(component_kind):
                for fill_mode in ("zero_bg", "original_bg"):
                    for transform_name in transforms:
                        rules.append(
                            RuleCandidate(
                                name=f"component_program:{source_name}:{component_kind}:{component_selector}:{fill_mode}:{transform_name}",
                                family="object_extract",
                                priority=100,
                                apply=lambda grid, sn=source_name, ck=component_kind, cs=component_selector, fm=fill_mode, tn=transform_name: extract_selected_component(
                                    grid,
                                    sn,
                                    ck,
                                    cs,
                                    fm,
                                    tn,
                                ),
                                metadata={
                                    "source_name": source_name,
                                    "component_kind": component_kind,
                                    "component_selector": component_selector,
                                    "fill_mode": fill_mode,
                                    "transform": transform_name,
                                },
                            )
                        )
    return rules


def infer_canvas_rules(train: list[Pair]) -> list[RuleCandidate]:
    shape_mode = consistent_output_shape_mode(train)
    if shape_mode is None:
        return []
    shape_mode_name, fixed_shape = shape_mode
    source_names = ["whole", "region:largest_area", "region:top_left", "region:top_right", "region:bottom_left", "region:bottom_right"]
    transforms = ["identity", "rot180", "flip_h", "flip_v"]
    anchors = ["top_left", "top_right", "bottom_left", "bottom_right", "center"]
    canvas_modes = ["blank", "input_without_selected"]
    fill_modes = ["zero", "input_bg"]
    rules = []
    for source_name in source_names:
        for component_kind in ("color", "foreground"):
            for component_selector in selectors_for_component_kind(component_kind):
                for transform_name in transforms:
                    for anchor_name in anchors:
                        for canvas_mode in canvas_modes:
                            for canvas_fill_mode in fill_modes:
                                if canvas_mode != "blank" and canvas_fill_mode != "input_bg":
                                    continue
                                rules.append(
                                    RuleCandidate(
                                        name=(
                                            f"canvas_program:{shape_mode_name}:{source_name}:{component_kind}:{component_selector}:"
                                            f"{transform_name}:{canvas_mode}:{canvas_fill_mode}:{anchor_name}"
                                        ),
                                        family="object_canvas",
                                        priority=120,
                                        apply=lambda grid, sn=source_name, ck=component_kind, cs=component_selector, tn=transform_name, cm=canvas_mode, cfm=canvas_fill_mode, an=anchor_name, fs=fixed_shape: build_canvas_program(
                                            grid,
                                            sn,
                                            ck,
                                            cs,
                                            "zero_bg",
                                            tn,
                                            cm,
                                            cfm,
                                            an,
                                            fs,
                                            None,
                                        ),
                                        metadata={
                                            "shape_mode": shape_mode_name,
                                            "source_name": source_name,
                                            "component_kind": component_kind,
                                            "component_selector": component_selector,
                                            "transform": transform_name,
                                            "canvas_mode": canvas_mode,
                                            "canvas_fill_mode": canvas_fill_mode,
                                            "anchor": anchor_name,
                                        },
                                    )
                                )
    return rules


def infer_object_rules(train: list[Pair]) -> list[RuleCandidate]:
    return (
        infer_region_extract_rules()
        + infer_component_program_rules()
        + infer_canvas_rules(train)
        + infer_move_copy_rules(train)
        + infer_group_rules()
        + infer_relation_crop_rules()
        + infer_relative_paint_rules(train)
    )


def infer_rules(train: list[Pair]) -> list[RuleCandidate]:
    base_rules = base.base_rule_candidates(train)
    object_rules = infer_object_rules(train)
    lifted = base.lift_shared_color_map_rules(train, base_rules + object_rules)
    rules = base.unique_rules_by_name(base_rules + object_rules + lifted)
    scored = [base.score_rule_on_train(rule, train) for rule in rules]
    scored.sort(key=lambda rule: (-rule.train_correct, rule.priority, rule.name))
    return scored


def filter_task_ids(
    challenges: dict,
    split_name: str,
    tag: str | None,
    primary_family: str | None,
    max_tasks: int | None,
) -> list[str]:
    task_ids = list(challenges)
    if tag is None and primary_family is None:
        return task_ids[:max_tasks] if max_tasks is not None else task_ids

    tags_path = repo_root() / "analysis" / "task_taxonomy" / f"{split_name}_tags.jsonl"
    rows = load_jsonl(tags_path)
    allowed = []
    for row in rows:
        if primary_family is not None and row["primary_family"] != primary_family:
            continue
        if tag is not None and tag not in row["tags"]:
            continue
        allowed.append(row["task_id"])
    if max_tasks is not None:
        allowed = allowed[:max_tasks]
    return [task_id for task_id in task_ids if task_id in set(allowed)]


def summarize_records(records: list[dict]) -> dict:
    total = len(records)
    exact_records = sum(1 for record in records if record["exact_rule_candidate_count"] > 0)
    partial_records = sum(1 for record in records if record["best_train_rule_correct"] > 0)
    return {
        "num_records": total,
        "records_with_exact_rule_candidate": exact_records,
        "exact_rule_record_rate": round(exact_records / total, 6) if total else 0.0,
        "records_with_partial_rule_candidate": partial_records,
        "partial_rule_record_rate": round(partial_records / total, 6) if total else 0.0,
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
    tag: str | None,
    primary_family: str | None,
) -> dict:
    challenges_path = data_dir / f"arc-agi_{split_name}_challenges.json"
    challenges = load_json(challenges_path)
    task_ids = filter_task_ids(challenges, split_name, tag, primary_family, max_tasks)

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
            attempts, sources = base.build_attempts(test_pair["input"], rules, train_total)
            submission[task_id].append({"attempt_1": attempts[0], "attempt_2": attempts[1]})
            record = {
                "task_id": task_id,
                "task_order": task_order,
                "test_index": test_index,
                "split_name": split_name,
                "rule_version": RULE_VERSION,
                "num_train_examples": train_total,
                "num_rules_considered": len(rules),
                "exact_rule_candidate_count": exact_rule_count,
                "best_train_rule_correct": best_train_rule_correct,
                "top_rules": top_rules,
                "attempt_sources": sources,
                "attempt_shapes": [list(base.shape(attempts[0])), list(base.shape(attempts[1]))],
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
            "tag": tag,
            "primary_family": primary_family,
            "rule_version": RULE_VERSION,
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
    parser.add_argument("--data-dir", type=Path, default=repo_root())
    parser.add_argument("--split-name", choices=["training", "evaluation", "test"], default="evaluation")
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    parser.add_argument("--max-tasks", type=int)
    parser.add_argument("--tag", type=str)
    parser.add_argument("--primary-family", type=str)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_solver(
        data_dir=args.data_dir,
        split_name=args.split_name,
        output_dir=args.output_dir,
        max_tasks=args.max_tasks,
        tag=args.tag,
        primary_family=args.primary_family,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
