#!/usr/bin/env python3
"""Summarize a downloaded Kaggle ARC baseline run directory."""

from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter
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


def load_scorer_module(repo_root: Path):
    scorer_path = repo_root / "scripts" / "score_submission_by_taxonomy.py"
    spec = importlib.util.spec_from_file_location("score_submission_by_taxonomy", scorer_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def summarize_records(records: list[dict]) -> dict:
    if not records:
        return {}
    prompt_version = Counter(r.get("prompt_version", "unknown") for r in records)
    fallback_count = sum(bool(r.get("used_fallback")) for r in records)
    parsed_count = sum(bool(r.get("parsed_ok")) for r in records)
    model_errors = Counter(r.get("error_type", "none") for r in records if r.get("error_type"))
    shape_eligible = [r for r in records if r.get("expected_shape") is not None]
    shape_correct = sum(
        tuple(r.get("attempt_shapes", [[-1, -1]])[0]) == tuple(r["expected_shape"])
        for r in shape_eligible
    )

    verification_records = [
        item
        for record in records
        for item in record.get("verification_records", [])
    ]
    hidden_exact = sum(bool(item.get("hidden_correct")) for item in verification_records)
    parsed_bundles = sum(
        bool(item.get("hidden_parsed")) and bool(item.get("test_parsed"))
        for item in verification_records
    )
    tasks_with_verified_candidate = sum((record.get("best_verified_votes") or 0) >= 1 for record in records)
    return {
        "num_records": len(records),
        "parsed_ok": parsed_count,
        "parsed_rate": round(parsed_count / len(records), 6),
        "used_fallback": fallback_count,
        "fallback_rate": round(fallback_count / len(records), 6),
        "shape_correct": shape_correct,
        "shape_correct_rate": round(shape_correct / len(shape_eligible), 6) if shape_eligible else None,
        "shape_eligible_records": len(shape_eligible),
        "tasks_with_verified_candidate": tasks_with_verified_candidate,
        "tasks_with_verified_candidate_rate": round(tasks_with_verified_candidate / len(records), 6),
        "verification_bundle_count": len(verification_records),
        "verification_bundle_parse_rate": (
            round(parsed_bundles / len(verification_records), 6) if verification_records else None
        ),
        "hidden_train_exact": hidden_exact,
        "hidden_train_exact_rate": (
            round(hidden_exact / len(verification_records), 6) if verification_records else None
        ),
        "prompt_versions": dict(prompt_version),
        "error_types": dict(model_errors.most_common()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True, help="Downloaded Kaggle artifact directory.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Local repo root containing dataset, taxonomy, and scorer.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output JSON path. Defaults to <run-dir>/local_summary.json",
    )
    args = parser.parse_args()

    run_dir = args.run_dir
    repo_root = args.repo_root
    output = args.output or (run_dir / "local_summary.json")

    report: dict = {"run_dir": str(run_dir)}

    config_path = run_dir / "run_config.json"
    submission_path = run_dir / "submission.json"
    task_records_path = run_dir / "task_records.jsonl"

    if config_path.exists():
        report["run_config"] = load_json(config_path)

    if task_records_path.exists():
        records = load_jsonl(task_records_path)
        report["artifact_summary"] = summarize_records(records)

    if submission_path.exists():
        split_name = report.get("run_config", {}).get("split_name", "")
        if split_name == "evaluation":
            scorer = load_scorer_module(repo_root)
            tags = scorer.load_jsonl(repo_root / "analysis" / "task_taxonomy" / "evaluation_tags.jsonl")
            solutions = scorer.load_json(repo_root / "arc-agi_evaluation_solutions.json")
            submission = scorer.load_json(submission_path)
            report["taxonomy_score_full_eval"] = scorer.score_submission(tags, solutions, submission)
            report["taxonomy_score_covered_tasks"] = scorer.score_submission(
                tags,
                solutions,
                submission,
                restrict_task_ids=submission.keys(),
            )
        else:
            report["taxonomy_score_full_eval"] = None
            report["taxonomy_score_covered_tasks"] = None
            report["note"] = "No ground-truth scoring was run because the artifact split is not evaluation."

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
