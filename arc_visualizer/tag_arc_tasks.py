#!/usr/bin/env python3
"""Build a first-pass multi-label taxonomy for ARC tasks.

The goal is not to perfectly solve the tasks. The goal is to create stable,
deterministic slices so baseline systems can be evaluated per-category and
synthetic data can later target weak regions.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Callable, Iterable

Grid = list[list[int]]
Pair = dict[str, Grid]
Task = dict[str, list[Pair]]


def load_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def shape(grid: Grid) -> tuple[int, int]:
    return len(grid), len(grid[0]) if grid else 0


def area(grid: Grid) -> int:
    h, w = shape(grid)
    return h * w


def flatten(grid: Grid) -> list[int]:
    return [cell for row in grid for cell in row]


def transpose(grid: Grid) -> Grid:
    return [list(row) for row in zip(*grid)]


def flip_h(grid: Grid) -> Grid:
    return [list(reversed(row)) for row in grid]


def flip_v(grid: Grid) -> Grid:
    return list(reversed(grid))


def rot90(grid: Grid) -> Grid:
    return flip_h(transpose(grid))


def rot180(grid: Grid) -> Grid:
    return flip_v(flip_h(grid))


def rot270(grid: Grid) -> Grid:
    return flip_v(transpose(grid))


def anti_transpose(grid: Grid) -> Grid:
    return rot180(transpose(grid))


TRANSFORMS: dict[str, Callable[[Grid], Grid]] = {
    "identity": lambda g: [row[:] for row in g],
    "rot90": rot90,
    "rot180": rot180,
    "rot270": rot270,
    "flip_h": flip_h,
    "flip_v": flip_v,
    "transpose": transpose,
    "anti_transpose": anti_transpose,
}


def grid_equal(a: Grid, b: Grid) -> bool:
    return a == b


def most_common_color(grid: Grid) -> int:
    counts = Counter(flatten(grid))
    return max(counts.items(), key=lambda kv: (kv[1], -kv[0]))[0]


def foreground_ratio(grid: Grid, bg: int) -> float:
    values = flatten(grid)
    if not values:
        return 0.0
    fg = sum(cell != bg for cell in values)
    return fg / len(values)


def bbox_of_non_bg(grid: Grid, bg: int) -> tuple[int, int, int, int] | None:
    coords = [(r, c) for r, row in enumerate(grid) for c, cell in enumerate(row) if cell != bg]
    if not coords:
        return None
    rows = [r for r, _ in coords]
    cols = [c for _, c in coords]
    return min(rows), max(rows), min(cols), max(cols)


def crop(grid: Grid, box: tuple[int, int, int, int]) -> Grid:
    r0, r1, c0, c1 = box
    return [row[c0 : c1 + 1] for row in grid[r0 : r1 + 1]]


def connected_components_by_color(grid: Grid, bg: int) -> list[dict]:
    h, w = shape(grid)
    seen = [[False] * w for _ in range(h)]
    comps: list[dict] = []
    for r in range(h):
        for c in range(w):
            color = grid[r][c]
            if seen[r][c] or color == bg:
                continue
            stack = [(r, c)]
            seen[r][c] = True
            cells = []
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
                    "bbox": (min(rows), max(rows), min(cols), max(cols)),
                }
            )
    return comps


def symmetry_tags(grid: Grid, prefix: str) -> list[str]:
    tags = []
    if grid_equal(grid, flip_h(grid)):
        tags.append(f"{prefix}_sym_horizontal")
    if grid_equal(grid, flip_v(grid)):
        tags.append(f"{prefix}_sym_vertical")
    if grid_equal(grid, rot180(grid)):
        tags.append(f"{prefix}_sym_rot180")
    return tags


def color_map_if_exists(src: Grid, dst: Grid) -> dict[int, int] | None:
    if shape(src) != shape(dst):
        return None
    mapping: dict[int, int] = {}
    for s_row, d_row in zip(src, dst):
        for s, d in zip(s_row, d_row):
            if s in mapping and mapping[s] != d:
                return None
            mapping[s] = d
    return mapping


def detect_global_transform(inp: Grid, out: Grid) -> str | None:
    for name, fn in TRANSFORMS.items():
        if grid_equal(fn(inp), out):
            return name
    return None


def detect_global_transform_with_color_map(inp: Grid, out: Grid) -> tuple[str, dict[int, int]] | None:
    for name, fn in TRANSFORMS.items():
        transformed = fn(inp)
        mapping = color_map_if_exists(transformed, out)
        if mapping is not None:
            return name, mapping
    return None


def is_tiled(base: Grid, out: Grid) -> bool:
    bh, bw = shape(base)
    oh, ow = shape(out)
    if bh == 0 or bw == 0 or oh % bh != 0 or ow % bw != 0:
        return False
    if oh == bh and ow == bw:
        return False
    for r in range(oh):
        for c in range(ow):
            if out[r][c] != base[r % bh][c % bw]:
                return False
    return True


def color_tile_map_if_exists(base: Grid, out: Grid) -> dict[int, int] | None:
    bh, bw = shape(base)
    oh, ow = shape(out)
    if bh == 0 or bw == 0 or oh % bh != 0 or ow % bw != 0:
        return None
    if oh == bh and ow == bw:
        return None
    mapping: dict[int, int] = {}
    for r in range(oh):
        for c in range(ow):
            src = base[r % bh][c % bw]
            dst = out[r][c]
            if src in mapping and mapping[src] != dst:
                return None
            mapping[src] = dst
    return mapping


def detect_tiling(inp: Grid, out: Grid) -> tuple[str, str] | None:
    for name, fn in TRANSFORMS.items():
        transformed = fn(inp)
        if is_tiled(transformed, out):
            return name, "tile_repeat"
        mapping = color_tile_map_if_exists(transformed, out)
        if mapping is not None:
            recolored = [[mapping[cell] for cell in row] for row in transformed]
            if is_tiled(recolored, out):
                return name, "tile_repeat_color_map"
    return None


def detect_crop_subgrid(inp: Grid, out: Grid) -> bool:
    oh, ow = shape(out)
    ih, iw = shape(inp)
    if oh > ih or ow > iw:
        return False
    for r0 in range(ih - oh + 1):
        for c0 in range(iw - ow + 1):
            if grid_equal([row[c0 : c0 + ow] for row in inp[r0 : r0 + oh]], out):
                return True
    return False


def detect_foreground_bbox_crop(inp: Grid, out: Grid) -> bool:
    bg = most_common_color(inp)
    box = bbox_of_non_bg(inp, bg)
    if box is None:
        return False
    return grid_equal(crop(inp, box), out)


def consistent(values: Iterable[str | bool | None]) -> str | bool | None:
    values = list(values)
    if not values:
        return None
    first = values[0]
    if all(v == first for v in values):
        return first
    return None


def bucket_num_colors(n: float) -> str:
    if n <= 3:
        return "low_color"
    if n <= 5:
        return "mid_color"
    return "high_color"


def bucket_grid_side(n: int) -> str:
    if n <= 10:
        return "small_grid"
    if n <= 20:
        return "medium_grid"
    return "large_grid"


def bucket_num_objects(n: float) -> str:
    if n <= 1.5:
        return "single_object"
    if n <= 4.5:
        return "multi_object"
    return "many_objects"


def bucket_foreground_ratio(x: float) -> str:
    if x < 0.15:
        return "very_sparse_fg"
    if x < 0.35:
        return "sparse_fg"
    if x < 0.65:
        return "mixed_density"
    return "dense_fg"


def analyze_task(task_id: str, task: Task) -> dict:
    train = task["train"]
    pair_infos = []
    input_color_counts = []
    output_color_counts = []
    input_object_counts = []
    output_object_counts = []
    fg_ratios = []
    max_side = 0
    input_areas = []
    output_areas = []
    shared_input_sym = None
    shared_output_sym = None

    for pair in train:
        inp = pair["input"]
        out = pair["output"]
        ih, iw = shape(inp)
        oh, ow = shape(out)
        max_side = max(max_side, ih, iw, oh, ow)
        input_areas.append(area(inp))
        output_areas.append(area(out))

        in_bg = most_common_color(inp)
        out_bg = most_common_color(out)
        input_color_counts.append(len(set(flatten(inp))))
        output_color_counts.append(len(set(flatten(out))))
        input_object_counts.append(len(connected_components_by_color(inp, in_bg)))
        output_object_counts.append(len(connected_components_by_color(out, out_bg)))
        fg_ratios.append(foreground_ratio(inp, in_bg))

        in_sym = tuple(symmetry_tags(inp, "input"))
        out_sym = tuple(symmetry_tags(out, "output"))
        shared_input_sym = set(in_sym) if shared_input_sym is None else shared_input_sym.intersection(in_sym)
        shared_output_sym = set(out_sym) if shared_output_sym is None else shared_output_sym.intersection(out_sym)

        pair_infos.append(
            {
                "shape_relation": (
                    "same_shape"
                    if (ih, iw) == (oh, ow)
                    else "shape_expand"
                    if oh * ow > ih * iw
                    else "shape_shrink"
                ),
                "transform": detect_global_transform(inp, out),
                "transform_with_color_map": detect_global_transform_with_color_map(inp, out),
                "crop_subgrid": detect_crop_subgrid(inp, out),
                "crop_foreground_bbox": detect_foreground_bbox_crop(inp, out),
                "direct_color_map": color_map_if_exists(inp, out),
                "tile": detect_tiling(inp, out),
            }
        )

    tags: set[str] = set()

    shape_relations = [p["shape_relation"] for p in pair_infos]
    shape_relation = consistent(shape_relations)
    if shape_relation is None:
        tags.add("shape_mixed")
    else:
        tags.add(shape_relation)

    tags.add(bucket_num_colors(mean(input_color_counts + output_color_counts)))
    tags.add(bucket_grid_side(max_side))
    tags.add(bucket_num_objects(mean(input_object_counts)))
    tags.add(bucket_foreground_ratio(mean(fg_ratios)))

    if mean(output_object_counts) > mean(input_object_counts) + 0.5:
        tags.add("object_count_increase")
    elif mean(output_object_counts) < mean(input_object_counts) - 0.5:
        tags.add("object_count_decrease")
    else:
        tags.add("object_count_stable")

    if shared_input_sym:
        tags.update(shared_input_sym)
    if shared_output_sym:
        tags.update(shared_output_sym)

    direct_maps = [p["direct_color_map"] is not None for p in pair_infos]
    if all(direct_maps) and tags.intersection({"same_shape"}):
        tags.add("global_color_map_per_pair")

    transform_names = [p["transform"] for p in pair_infos]
    transform_name = consistent(transform_names)
    if transform_name is not None:
        tags.add("global_geo_transform")
        tags.add(f"geo_{transform_name}")

    transform_with_map = [p["transform_with_color_map"][0] if p["transform_with_color_map"] else None for p in pair_infos]
    transform_with_map_name = consistent(transform_with_map)
    if transform_with_map_name is not None:
        tags.add("geo_transform_with_color_map")
        tags.add(f"geo_color_{transform_with_map_name}")

    if all(p["crop_subgrid"] for p in pair_infos):
        tags.add("crop_subgrid")
    if all(p["crop_foreground_bbox"] for p in pair_infos):
        tags.add("crop_foreground_bbox")

    tile_kind = consistent([p["tile"][1] if p["tile"] else None for p in pair_infos])
    tile_transform = consistent([p["tile"][0] if p["tile"] else None for p in pair_infos])
    if tile_kind is not None:
        tags.add(tile_kind)
        if tile_transform is not None:
            tags.add(f"tile_from_{tile_transform}")

    simple_tags = {
        "global_geo_transform",
        "geo_transform_with_color_map",
        "global_color_map_per_pair",
        "crop_subgrid",
        "crop_foreground_bbox",
        "tile_repeat",
        "tile_repeat_color_map",
    }
    if not tags.intersection(simple_tags):
        tags.add("compositional_or_other")

    if tags.intersection({"shape_expand", "shape_shrink", "shape_mixed"}) and "compositional_or_other" in tags:
        tags.add("hard_shape_reasoning")
    if "many_objects" in tags and "compositional_or_other" in tags:
        tags.add("hard_object_reasoning")
    if "large_grid" in tags and "compositional_or_other" in tags:
        tags.add("hard_large_grid")

    primary_family = "compositional_or_other"
    priority = [
        "tile_repeat_color_map",
        "tile_repeat",
        "crop_foreground_bbox",
        "crop_subgrid",
        "geo_transform_with_color_map",
        "global_geo_transform",
        "global_color_map_per_pair",
        "compositional_or_other",
    ]
    for tag in priority:
        if tag in tags:
            primary_family = tag
            break

    return {
        "task_id": task_id,
        "num_train_examples": len(train),
        "num_test_examples": len(task["test"]),
        "avg_input_area": round(mean(input_areas), 2),
        "avg_output_area": round(mean(output_areas), 2),
        "max_side": max_side,
        "avg_input_colors": round(mean(input_color_counts), 2),
        "avg_output_colors": round(mean(output_color_counts), 2),
        "avg_input_objects": round(mean(input_object_counts), 2),
        "avg_output_objects": round(mean(output_object_counts), 2),
        "avg_fg_ratio": round(mean(fg_ratios), 4),
        "primary_family": primary_family,
        "tags": sorted(tags),
    }


def analyze_split(split_name: str, challenges_path: Path) -> list[dict]:
    tasks = load_json(challenges_path)
    rows = [analyze_task(task_id, task) for task_id, task in tasks.items()]
    rows.sort(key=lambda row: row["task_id"])
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def summarize(rows: list[dict]) -> dict:
    primary = Counter(row["primary_family"] for row in rows)
    tags = Counter(tag for row in rows for tag in row["tags"])
    return {
        "num_tasks": len(rows),
        "primary_family_counts": dict(primary.most_common()),
        "tag_counts": dict(tags.most_common()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Directory containing ARC challenge JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "analysis" / "task_taxonomy",
        help="Directory where taxonomy artifacts will be written.",
    )
    args = parser.parse_args()

    split_to_file = {
        "training": "arc-agi_training_challenges.json",
        "evaluation": "arc-agi_evaluation_challenges.json",
        "test": "arc-agi_test_challenges.json",
    }

    combined_summary = {}
    for split, filename in split_to_file.items():
        rows = analyze_split(split, args.data_dir / filename)
        write_jsonl(args.output_dir / f"{split}_tags.jsonl", rows)
        summary = summarize(rows)
        combined_summary[split] = summary
        with (args.output_dir / f"{split}_summary.json").open("w") as f:
            json.dump(summary, f, indent=2)

    with (args.output_dir / "README.md").open("w") as f:
        f.write(
            "# ARC Task Taxonomy\n\n"
            "This directory contains deterministic, heuristic task tags for the ARC dataset.\n\n"
            "Use the `*_tags.jsonl` files to slice baseline performance by tag and by `primary_family`.\n"
        )

    with (args.output_dir / "all_summaries.json").open("w") as f:
        json.dump(combined_summary, f, indent=2)


if __name__ == "__main__":
    main()
