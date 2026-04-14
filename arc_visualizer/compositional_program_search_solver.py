#!/usr/bin/env python3
"""Bounded compositional ARC solver using preprocessor-program search."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import deterministic_arc_solver as base
import object_program_arc_solver as ops

Grid = list[list[int]]
Pair = dict[str, Grid]
RULE_VERSION = "compositional_program_v1"


@dataclass(frozen=True)
class Preprocessor:
    name: str
    family: str
    priority: int
    apply: Callable[[Grid], Grid | None]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_output_dir() -> Path:
    return repo_root() / "local_runs" / "compositional_program_search_solver"


def identity_preprocessor() -> Preprocessor:
    return Preprocessor(
        name="identity",
        family="identity",
        priority=0,
        apply=lambda grid: base.copy_grid(grid),
    )


def primitive_preprocessors() -> list[Preprocessor]:
    preprocessors = [identity_preprocessor()]

    for region_selector in ("largest_area", "top_left", "bottom_right"):
        preprocessors.append(
            Preprocessor(
                name=f"region:{region_selector}",
                family="region_select",
                priority=10,
                apply=lambda grid, rs=region_selector: ops.select_region(grid, rs),
            )
        )

    group_specs = [
        ("foreground", "touching_border", "input_remove_group"),
        ("foreground", "interior_only", "blank_same_shape"),
        ("foreground", "largest_size_group", "blank_same_shape"),
        ("foreground", "largest_size_group", "input_remove_group"),
        ("color", "least_freq_color_group", "blank_same_shape"),
        ("color", "most_freq_color_group", "blank_same_shape"),
    ]
    for component_kind, filter_name, canvas_mode in group_specs:
        preprocessors.append(
            Preprocessor(
                name=f"group_render:{component_kind}:{filter_name}:{canvas_mode}",
                family="group_render",
                priority=20,
                apply=lambda grid, ck=component_kind, fn=filter_name, cm=canvas_mode: ops.render_component_group(
                    grid,
                    ops.select_component_group(grid, ck, fn),
                    cm,
                ),
            )
        )

    crop_specs = [
        ("foreground", "largest_size_group", "full"),
        ("foreground", "largest_size_group", "group_only"),
        ("foreground", "touching_border", "group_only"),
        ("foreground", "interior_only", "full"),
        ("color", "least_freq_color_group", "full"),
        ("color", "most_freq_color_group", "full"),
    ]
    for component_kind, filter_name, mask_mode in crop_specs:
        preprocessors.append(
            Preprocessor(
                name=f"group_crop:{component_kind}:{filter_name}:{mask_mode}",
                family="group_crop",
                priority=15,
                apply=lambda grid, ck=component_kind, fn=filter_name, mm=mask_mode: ops.crop_union_of_component_group(
                    grid,
                    ck,
                    fn,
                    mm,
                    "identity",
                ),
            )
        )

    pair_specs = [
        ("foreground", "largest", "smallest", "full"),
        ("foreground", "largest", "smallest", "pair_only"),
        ("foreground", "top_left", "bottom_right", "full"),
        ("color", "least_freq_color", "most_freq_color", "full"),
        ("color", "least_freq_color", "most_freq_color", "pair_only"),
    ]
    for component_kind, first_selector, second_selector, mask_mode in pair_specs:
        preprocessors.append(
            Preprocessor(
                name=f"pair_crop:{component_kind}:{first_selector}:{second_selector}:{mask_mode}",
                family="pair_crop",
                priority=25,
                apply=lambda grid, ck=component_kind, fs=first_selector, ss=second_selector, mm=mask_mode: ops.crop_union_of_selected_components(
                    grid,
                    ck,
                    fs,
                    ss,
                    mm,
                    "identity",
                ),
            )
        )

    return preprocessors


def compose_preprocessors(chain: list[Preprocessor]) -> Preprocessor:
    if len(chain) == 1:
        return chain[0]

    def apply(grid: Grid, parts=tuple(chain)) -> Grid | None:
        current: Grid | None = base.copy_grid(grid)
        for pre in parts:
            current = pre.apply(current) if current is not None else None
            if current is None or not base.valid_grid(current):
                return None
        return current

    return Preprocessor(
        name="|".join(pre.name for pre in chain),
        family="|".join(pre.family for pre in chain),
        priority=sum(pre.priority for pre in chain),
        apply=apply,
    )


def enumerate_preprocessors(max_depth: int) -> list[Preprocessor]:
    primitives = primitive_preprocessors()
    identity = primitives[0]
    leaves = primitives[1:]
    preprocessors = [identity] + leaves
    if max_depth >= 2:
        for first in leaves:
            for second in leaves:
                preprocessors.append(compose_preprocessors([first, second]))
    return preprocessors


def transformed_train_pairs(train: list[Pair], preprocessor: Preprocessor) -> list[Pair] | None:
    transformed = []
    for pair in train:
        new_input = preprocessor.apply(pair["input"])
        if new_input is None or not base.valid_grid(new_input):
            return None
        transformed.append({"input": new_input, "output": pair["output"]})
    return transformed


def transformed_signature(train: list[Pair], preprocessor: Preprocessor) -> tuple[tuple[tuple[int, ...], ...], ...] | None:
    transformed = transformed_train_pairs(train, preprocessor)
    if transformed is None:
        return None
    return tuple(base.normalize_grid(pair["input"]) for pair in transformed)


def infer_inner_rules(train: list[Pair], max_inner_rules: int) -> list[base.RuleCandidate]:
    base_rules = base.base_rule_candidates(train)
    extra_rules = ops.infer_region_extract_rules() + ops.infer_move_copy_rules(train)
    seed_rules = base.unique_rules_by_name(base_rules + extra_rules)
    lifted = base.lift_shared_color_map_rules(train, seed_rules)
    rules = base.unique_rules_by_name(seed_rules + lifted)
    scored = [base.score_rule_on_train(rule, train) for rule in rules]
    scored.sort(key=lambda rule: (-rule.train_correct, rule.priority, rule.name))
    return [rule for rule in scored if rule.train_correct > 0][:max_inner_rules]


def compose_rule(preprocessor: Preprocessor, inner_rule: base.RuleCandidate) -> base.RuleCandidate:
    def apply(grid: Grid, pre=preprocessor, inner=inner_rule) -> Grid | None:
        transformed = pre.apply(grid)
        if transformed is None or not base.valid_grid(transformed):
            return None
        return inner.apply(transformed)

    return base.RuleCandidate(
        name=f"{preprocessor.name}|{inner_rule.name}",
        family=f"composite:{preprocessor.family}:{inner_rule.family}",
        priority=preprocessor.priority + inner_rule.priority,
        apply=apply,
        metadata={
            "preprocessor": preprocessor.name,
            "preprocessor_family": preprocessor.family,
            "inner_rule": inner_rule.name,
            "inner_family": inner_rule.family,
        },
        train_correct=inner_rule.train_correct,
        train_total=inner_rule.train_total,
    )


def infer_rules(
    train: list[Pair],
    max_preprocess_depth: int,
    max_inner_rules: int,
) -> tuple[list[base.RuleCandidate], dict[str, int]]:
    preprocessors = enumerate_preprocessors(max_preprocess_depth)
    seen_signatures: set[tuple[tuple[tuple[int, ...], ...], ...]] = set()
    composite_rules: list[base.RuleCandidate] = []
    stats = {
        "num_preprocessors_enumerated": len(preprocessors),
        "num_preprocessors_valid": 0,
        "num_preprocessors_unique": 0,
        "num_inner_rule_hits": 0,
    }

    for preprocessor in preprocessors:
        transformed = transformed_train_pairs(train, preprocessor)
        if transformed is None:
            continue
        stats["num_preprocessors_valid"] += 1
        signature = tuple(base.normalize_grid(pair["input"]) for pair in transformed)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        stats["num_preprocessors_unique"] += 1

        inner_rules = infer_inner_rules(transformed, max_inner_rules)
        stats["num_inner_rule_hits"] += len(inner_rules)
        for inner_rule in inner_rules:
            composite_rules.append(compose_rule(preprocessor, inner_rule))

    composite_rules = base.unique_rules_by_name(composite_rules)
    composite_rules.sort(key=lambda rule: (-rule.train_correct, rule.priority, rule.name))
    return composite_rules, stats


def run_solver(
    data_dir: Path,
    split_name: str,
    output_dir: Path,
    max_tasks: int | None,
    tag: str | None,
    primary_family: str | None,
    max_preprocess_depth: int,
    max_inner_rules: int,
) -> dict:
    challenges_path = data_dir / f"arc-agi_{split_name}_challenges.json"
    challenges = ops.load_json(challenges_path)
    task_ids = ops.filter_task_ids(challenges, split_name, tag, primary_family, max_tasks)

    output_dir.mkdir(parents=True, exist_ok=True)
    task_records_path = output_dir / "task_records.jsonl"
    if task_records_path.exists():
        task_records_path.unlink()

    start = time.time()
    submission = {}
    records = []

    for task_order, task_id in enumerate(task_ids, start=1):
        task = challenges[task_id]
        rules, search_stats = infer_rules(task["train"], max_preprocess_depth, max_inner_rules)
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
                "search_stats": search_stats,
                "elapsed_sec": round(time.time() - test_start, 4),
            }
            records.append(record)
            ops.append_jsonl(task_records_path, record)

    ops.dump_json(output_dir / "submission.json", submission)
    artifact_summary = ops.summarize_records(records)
    score_report = ops.maybe_score_submission(split_name, submission, task_ids)
    result = {
        "run_dir": str(output_dir),
        "config": {
            "data_dir": str(data_dir),
            "split_name": split_name,
            "output_dir": str(output_dir),
            "max_tasks": max_tasks,
            "tag": tag,
            "primary_family": primary_family,
            "max_preprocess_depth": max_preprocess_depth,
            "max_inner_rules": max_inner_rules,
            "rule_version": RULE_VERSION,
            "num_tasks_run": len(task_ids),
            "challenge_file": str(challenges_path),
            "total_elapsed_sec": round(time.time() - start, 4),
        },
        "artifact_summary": artifact_summary,
        "score_report": score_report,
    }
    ops.dump_json(output_dir / "local_summary.json", result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=repo_root())
    parser.add_argument("--split-name", choices=["training", "evaluation", "test"], default="evaluation")
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    parser.add_argument("--max-tasks", type=int)
    parser.add_argument("--tag", type=str)
    parser.add_argument("--primary-family", type=str)
    parser.add_argument("--max-preprocess-depth", type=int, default=2)
    parser.add_argument("--max-inner-rules", type=int, default=24)
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
        max_preprocess_depth=args.max_preprocess_depth,
        max_inner_rules=args.max_inner_rules,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
