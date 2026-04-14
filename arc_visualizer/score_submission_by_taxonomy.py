#!/usr/bin/env python3
"""Score ARC submissions overall and by taxonomy slices."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_json(path: Path):
    with path.open() as f:
        return json.load(f)


def load_jsonl(path: Path):
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def normalize_grid(grid):
    return tuple(tuple(int(cell) for cell in row) for row in grid)


def attempt_correct(pred_record, target_grid) -> bool:
    target = normalize_grid(target_grid)
    for key in ("attempt_1", "attempt_2"):
        pred = pred_record.get(key)
        if pred is None:
            continue
        try:
            if normalize_grid(pred) == target:
                return True
        except Exception:
            continue
    return False


def aggregate_bucket(records):
    total = len(records)
    correct = sum(r["correct"] for r in records)
    return {
        "count": total,
        "correct": correct,
        "accuracy": round(correct / total, 6) if total else 0.0,
        "task_ids": sorted({r["task_id"] for r in records}),
    }


def score_submission(tags_rows, solutions, submission, restrict_task_ids=None):
    tag_records = defaultdict(list)
    family_records = defaultdict(list)
    all_records = []
    missing_tasks = []
    malformed_outputs = []

    tags_by_task = {row["task_id"]: row for row in tags_rows}
    allowed_task_ids = None if restrict_task_ids is None else set(restrict_task_ids)

    for task_id, expected_outputs in solutions.items():
        if allowed_task_ids is not None and task_id not in allowed_task_ids:
            continue
        tag_row = tags_by_task.get(task_id)
        if tag_row is None:
            continue

        predicted_outputs = submission.get(task_id)
        if predicted_outputs is None:
            missing_tasks.append(task_id)
            predicted_outputs = []

        for idx, target_grid in enumerate(expected_outputs):
            pred_record = predicted_outputs[idx] if idx < len(predicted_outputs) else {}
            if not isinstance(pred_record, dict):
                malformed_outputs.append((task_id, idx))
                pred_record = {}

            correct = attempt_correct(pred_record, target_grid)
            record = {
                "task_id": task_id,
                "test_index": idx,
                "correct": correct,
                "primary_family": tag_row["primary_family"],
                "tags": tag_row["tags"],
            }
            all_records.append(record)
            family_records[tag_row["primary_family"]].append(record)
            for tag in tag_row["tags"]:
                tag_records[tag].append(record)

    overall = aggregate_bucket(all_records)
    by_family = {
        family: aggregate_bucket(records)
        for family, records in sorted(
            family_records.items(),
            key=lambda item: (-sum(r["correct"] for r in item[1]) / len(item[1]), item[0]),
        )
    }
    by_tag = {
        tag: aggregate_bucket(records)
        for tag, records in sorted(
            tag_records.items(),
            key=lambda item: (-sum(r["correct"] for r in item[1]) / len(item[1]), item[0]),
        )
    }

    missed_counter = Counter()
    for record in all_records:
        if record["correct"]:
            continue
        missed_counter[record["primary_family"]] += 1
        for tag in record["tags"]:
            missed_counter[tag] += 1

    return {
        "overall": overall,
        "by_primary_family": by_family,
        "by_tag": by_tag,
        "num_missing_tasks": len(missing_tasks),
        "missing_task_ids": sorted(missing_tasks),
        "num_malformed_outputs": len(malformed_outputs),
        "malformed_outputs": [{"task_id": task_id, "test_index": idx} for task_id, idx in malformed_outputs],
        "most_missed_buckets": dict(missed_counter.most_common(25)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, required=True, help="Path to submission.json")
    parser.add_argument(
        "--solutions",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "arc-agi_evaluation_solutions.json",
        help="Path to ground-truth solutions JSON.",
    )
    parser.add_argument(
        "--tags",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "analysis" / "task_taxonomy" / "evaluation_tags.jsonl",
        help="Path to taxonomy tags JSONL.",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path.")
    parser.add_argument(
        "--restrict-to-submission-tasks",
        action="store_true",
        help="Score only task IDs present in the submission file.",
    )
    args = parser.parse_args()

    tags_rows = load_jsonl(args.tags)
    solutions = load_json(args.solutions)
    submission = load_json(args.submission)

    restrict_task_ids = set(submission.keys()) if args.restrict_to_submission_tasks else None
    report = score_submission(tags_rows, solutions, submission, restrict_task_ids=restrict_task_ids)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w") as f:
            json.dump(report, f, indent=2)
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
