#!/usr/bin/env python3
"""Build a static dashboard dataset for ARC taxonomy and baseline runs."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LOCAL_RUNS_DIR = ROOT / "local_runs"
TAXONOMY_DIR = ROOT / "analysis" / "task_taxonomy"
DASHBOARD_DIR = ROOT / "analysis" / "task_dashboard"

PRIMARY_FAMILIES = [
    "crop_subgrid",
    "crop_foreground_bbox",
    "global_geo_transform",
    "geo_transform_with_color_map",
    "tile_repeat",
    "tile_repeat_color_map",
    "compositional_or_other",
]

RUN_FAMILY_ORDER = {
    "llm_prompt": 0,
    "deterministic": 1,
    "object_program": 2,
    "compositional": 3,
    "other": 4,
}


def load_json(path: Path) -> Any:
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


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2)


def dump_js_assignment(path: Path, var_name: str, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write(f"window.{var_name} = ")
        json.dump(data, f, indent=2)
        f.write(";\n")


def shape(grid: list[list[int]] | None) -> list[int] | None:
    if not isinstance(grid, list) or not grid:
        return None
    if not isinstance(grid[0], list):
        return None
    return [len(grid), len(grid[0])]


def grid_equal(a: list[list[int]] | None, b: list[list[int]] | None) -> bool:
    return a == b


def infer_run_family(run_id: str, cfg: dict) -> str:
    model_path = str(cfg.get("model_path") or "")
    rule_version = str(cfg.get("rule_version") or "")
    if model_path or run_id.startswith("eval_"):
        return "llm_prompt"
    if "deterministic" in run_id or "deterministic" in rule_version:
        return "deterministic"
    if "object_program" in run_id or "object_program" in rule_version:
        return "object_program"
    if "compositional" in run_id or "compositional" in rule_version:
        return "compositional"
    return "other"


def infer_split(run_id: str, cfg: dict, records: list[dict]) -> str | None:
    if cfg.get("split_name"):
        return cfg["split_name"]
    if records and records[0].get("split_name"):
        return records[0]["split_name"]
    lowered = run_id.lower()
    if "training" in lowered:
        return "training"
    if "evaluation" in lowered or "eval" in lowered:
        return "evaluation"
    if "test" in lowered:
        return "test"
    return None


def humanize_run_label(run_id: str, cfg: dict, family: str) -> str:
    if family == "llm_prompt":
        model = str(cfg.get("model_path") or run_id).split("/")[-1]
        prompt = str(cfg.get("prompt_version") or "")
        max_tasks = cfg.get("max_tasks")
        task_scope = f"slice {max_tasks}" if max_tasks else "full"
        if prompt:
            prompt = prompt.replace("arc_", "").replace("_", " ")
            return f"{model} • {prompt} • {task_scope}"
        return f"{model} • {task_scope}"
    return run_id.replace("_", " ")


def metric_label_pairs(summary: dict, family: str) -> list[dict]:
    artifact = summary.get("artifact_summary") or {}
    score = summary.get("score_report") or summary.get("taxonomy_score_full_eval") or {}
    overall = score.get("overall") or {}
    metrics = []
    if overall.get("accuracy") is not None:
        metrics.append({"label": "Accuracy", "value": round(overall["accuracy"], 4)})
    if artifact.get("exact_rule_record_rate") is not None:
        metrics.append({"label": "Exact rule rate", "value": round(artifact["exact_rule_record_rate"], 4)})
    if artifact.get("partial_rule_record_rate") is not None:
        metrics.append({"label": "Partial rule rate", "value": round(artifact["partial_rule_record_rate"], 4)})
    if artifact.get("parsed_rate") is not None:
        metrics.append({"label": "Parsed rate", "value": round(artifact["parsed_rate"], 4)})
    if artifact.get("fallback_rate") is not None:
        metrics.append({"label": "Fallback rate", "value": round(artifact["fallback_rate"], 4)})
    if artifact.get("verification_bundle_parse_rate") is not None:
        metrics.append({"label": "Verifier parse rate", "value": round(artifact["verification_bundle_parse_rate"], 4)})
    if artifact.get("tasks_with_verified_candidate_rate") is not None:
        metrics.append({"label": "Verified candidate rate", "value": round(artifact["tasks_with_verified_candidate_rate"], 4)})
    if artifact.get("hidden_train_exact_rate") is not None:
        metrics.append({"label": "Hidden-train exact rate", "value": round(artifact["hidden_train_exact_rate"], 4)})
    return metrics


def compute_task_status(
    records: list[dict],
    submission_rows: list[dict] | None,
    solutions: list | None,
) -> tuple[str, dict]:
    total_records = len(records)
    correct_records = 0
    exact_rule_records = 0
    train_signal_records = 0
    parsed_records = 0
    shape_match_records = 0
    fallback_records = 0
    best_train_rule_correct = 0
    top_rule_names: Counter[str] = Counter()
    record_details = []

    for idx, record in enumerate(records):
        sol = solutions[idx] if solutions and idx < len(solutions) else None
        submission = submission_rows[idx] if submission_rows and idx < len(submission_rows) else {}
        attempts = [submission.get("attempt_1"), submission.get("attempt_2")]
        attempt_correct = [grid_equal(attempt, sol) for attempt in attempts] if sol is not None else [False, False]
        record_correct = any(attempt_correct)
        correct_records += int(record_correct)

        exact_rule = int(record.get("exact_rule_candidate_count", 0) or 0) > 0 or any(
            source.get("bucket") == "exact" for source in record.get("attempt_sources", [])
        )
        exact_rule_records += int(exact_rule)

        partial_train = int(record.get("best_train_rule_correct", 0) or 0) > 0
        train_signal_records += int(partial_train or exact_rule)
        best_train_rule_correct = max(best_train_rule_correct, int(record.get("best_train_rule_correct", 0) or 0))

        parsed = bool(record.get("parsed_ok")) or any(record.get("parsed_attempts", []) or [])
        parsed_records += int(parsed)

        sol_shape = shape(sol) if sol is not None else None
        sub_shapes = [shape(attempt) for attempt in attempts]
        shape_match = bool(sol_shape) and any(attempt_shape == sol_shape for attempt_shape in sub_shapes if attempt_shape)
        shape_match_records += int(shape_match)

        attempt_sources = record.get("attempt_sources", []) or []
        fallback = bool(record.get("used_fallback")) or (
            bool(attempt_sources)
            and all(source.get("bucket") == "fallback" for source in attempt_sources)
        )
        fallback_records += int(fallback)

        if attempt_sources:
            top_rule_names.update(source.get("rule_name", "") for source in attempt_sources if source.get("rule_name"))

        record_details.append(
            {
                "test_index": record.get("test_index"),
                "correct": record_correct,
                "parsed": parsed,
                "shape_match": shape_match,
                "fallback": fallback,
                "exact_rule_candidate_count": int(record.get("exact_rule_candidate_count", 0) or 0),
                "best_train_rule_correct": int(record.get("best_train_rule_correct", 0) or 0),
                "attempt_shapes": record.get("attempt_shapes"),
                "attempt_sources": attempt_sources[:2],
                "top_rules": record.get("top_rules", [])[:4],
                "search_stats": record.get("search_stats"),
            }
        )

    if total_records and correct_records == total_records:
        status = "solved"
    elif correct_records > 0 or exact_rule_records > 0 or train_signal_records > 0:
        status = "partial"
    elif parsed_records > 0 or shape_match_records > 0:
        status = "structural"
    else:
        status = "unsolved"

    detail = {
        "status": status,
        "records_total": total_records,
        "records_correct": correct_records,
        "records_with_exact_rule": exact_rule_records,
        "records_with_train_signal": train_signal_records,
        "records_parsed": parsed_records,
        "records_shape_match": shape_match_records,
        "records_fallback": fallback_records,
        "best_train_rule_correct": best_train_rule_correct,
        "top_rule_names": [name for name, _ in top_rule_names.most_common(6)],
        "record_details": record_details,
    }
    return status, detail


def aggregate_taxonomy(rows: list[dict]) -> dict:
    primary = Counter(row["primary_family"] for row in rows)
    tags = Counter(tag for row in rows for tag in row["tags"])
    return {
        "num_tasks": len(rows),
        "primary_family_counts": dict(sorted(primary.items(), key=lambda item: (-item[1], item[0]))),
        "tag_counts": dict(sorted(tags.items(), key=lambda item: (-item[1], item[0]))),
    }


def build_taxonomy_payload() -> tuple[dict[str, list[dict]], dict[str, dict]]:
    rows_by_split: dict[str, list[dict]] = {}
    summaries_by_split: dict[str, dict] = {}
    for split in ("training", "evaluation", "test"):
        rows = load_jsonl(TAXONOMY_DIR / f"{split}_tags.jsonl")
        rows.sort(key=lambda row: (PRIMARY_FAMILIES.index(row["primary_family"]) if row["primary_family"] in PRIMARY_FAMILIES else 999, row["task_id"]))
        rows_by_split[split] = rows
        summaries_by_split[split] = aggregate_taxonomy(rows)
    return rows_by_split, summaries_by_split


def build_run_payload(rows_by_split: dict[str, list[dict]]) -> dict[str, dict]:
    taxonomy_by_split = {
        split: {row["task_id"]: row for row in rows}
        for split, rows in rows_by_split.items()
    }
    solutions_by_split = {}
    for split in ("training", "evaluation"):
        path = ROOT / f"arc-agi_{split}_solutions.json"
        if path.exists():
            solutions_by_split[split] = load_json(path)

    run_payload: dict[str, dict] = {}
    for summary_path in sorted(LOCAL_RUNS_DIR.glob("*/local_summary.json")):
        run_dir = summary_path.parent
        run_id = run_dir.name
        if run_id.startswith("smoke_"):
            continue

        summary = load_json(summary_path)
        cfg = dict(summary.get("config") or {})
        cfg.update(summary.get("run_config") or {})
        records_path = run_dir / "task_records.jsonl"
        records = load_jsonl(records_path) if records_path.exists() else []
        split = infer_split(run_id, cfg, records)
        if split not in taxonomy_by_split:
            continue

        family = infer_run_family(run_id, cfg)
        label = humanize_run_label(run_id, cfg, family)
        summary_metrics = metric_label_pairs(summary, family)

        records_by_task: dict[str, list[dict]] = defaultdict(list)
        for record in records:
            records_by_task[record["task_id"]].append(record)
        for task_records in records_by_task.values():
            task_records.sort(key=lambda row: row.get("test_index", 0))

        submission_path = run_dir / "submission.json"
        submission = load_json(submission_path) if submission_path.exists() else {}
        split_solutions = solutions_by_split.get(split, {})

        task_statuses = {}
        status_counts = Counter()
        family_summary = defaultdict(lambda: Counter())
        tag_summary = defaultdict(lambda: Counter())

        for task_id, task_records in records_by_task.items():
            submission_rows = submission.get(task_id)
            solutions = split_solutions.get(task_id)
            status, detail = compute_task_status(task_records, submission_rows, solutions)
            task_statuses[task_id] = detail
            status_counts[status] += 1

            taxonomy = taxonomy_by_split[split].get(task_id)
            if taxonomy:
                family_summary[taxonomy["primary_family"]]["covered"] += 1
                family_summary[taxonomy["primary_family"]][status] += 1
                for tag in taxonomy["tags"]:
                    tag_summary[tag]["covered"] += 1
                    tag_summary[tag][status] += 1

        task_coverage = len(task_statuses)
        run_payload[run_id] = {
            "id": run_id,
            "label": label,
            "family": family,
            "family_order": RUN_FAMILY_ORDER.get(family, 99),
            "split": split,
            "scope": {
                "max_tasks": cfg.get("max_tasks"),
                "tag": cfg.get("tag"),
                "primary_family": cfg.get("primary_family"),
                "num_tasks_run": cfg.get("num_tasks_run"),
            },
            "summary": {
                "task_coverage": task_coverage,
                "status_counts": dict(status_counts),
                "summary_metrics": summary_metrics,
                "artifact_summary": summary.get("artifact_summary"),
            },
            "task_statuses": task_statuses,
            "family_summary": {
                family_name: dict(counter)
                for family_name, counter in sorted(family_summary.items())
            },
            "tag_summary": {
                tag: dict(counter)
                for tag, counter in sorted(tag_summary.items())
            },
        }
    return run_payload


def build_payload() -> dict:
    rows_by_split, summaries_by_split = build_taxonomy_payload()
    runs = build_run_payload(rows_by_split)
    splits = {}
    for split, rows in rows_by_split.items():
        task_rows = []
        for row in rows:
            task_rows.append(
                {
                    "task_id": row["task_id"],
                    "primary_family": row["primary_family"],
                    "tags": row["tags"],
                    "num_train_examples": row["num_train_examples"],
                    "num_test_examples": row["num_test_examples"],
                    "avg_input_area": row["avg_input_area"],
                    "avg_output_area": row["avg_output_area"],
                    "max_side": row["max_side"],
                    "avg_input_colors": row["avg_input_colors"],
                    "avg_output_colors": row["avg_output_colors"],
                    "avg_input_objects": row["avg_input_objects"],
                    "avg_output_objects": row["avg_output_objects"],
                    "avg_fg_ratio": row["avg_fg_ratio"],
                }
            )
        splits[split] = {
            "summary": summaries_by_split[split],
            "tasks": task_rows,
            "run_ids": sorted(
                [run_id for run_id, run in runs.items() if run["split"] == split],
                key=lambda run_id: (
                    runs[run_id]["family_order"],
                    -(runs[run_id]["summary"]["task_coverage"]),
                    run_id,
                ),
            ),
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "splits": splits,
        "runs": runs,
        "primary_families": PRIMARY_FAMILIES,
    }


def main() -> None:
    payload = build_payload()
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    dump_json(DASHBOARD_DIR / "dashboard_data.json", payload)
    dump_js_assignment(DASHBOARD_DIR / "dashboard_data.js", "ARC_DASHBOARD_DATA", payload)
    print(json.dumps({"dashboard_dir": str(DASHBOARD_DIR), "runs": len(payload["runs"])}, indent=2))


if __name__ == "__main__":
    main()
