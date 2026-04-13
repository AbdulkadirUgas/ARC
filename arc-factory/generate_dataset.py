"""Generate a dataset for all mechanics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

from generators.mechanics import MECHANICS, generate
from validator import validate_task

Task = Dict[str, Any]


def _write_jsonl(tasks: List[Task], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for task in tasks:
            f.write(json.dumps(task) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate dataset for all mechanics")
    parser.add_argument("--count", type=int, default=5, help="Tasks per mechanic")
    parser.add_argument("--out", type=str, default="new_dataset.jsonl", help="Output JSONL file")
    parser.add_argument("--validate", action="store_true", help="Run validator checks")
    parser.add_argument("--seed", type=int, default=None, help="Base seed for reproducibility")
    args = parser.parse_args()

    tasks: List[Task] = []
    for mechanic in sorted(MECHANICS.keys()):
        for i in range(args.count):
            seed = None if args.seed is None else args.seed + i
            task = generate(mechanic, seed=seed)
            task_meta = task.get("meta", {})
            task_meta.update({"generator": "mechanics", "mechanic": mechanic, "seed": seed})
            task["meta"] = task_meta
            if args.validate:
                ok, errors = validate_task(task)
                if not ok:
                    task["meta"]["validation_errors"] = errors
                    continue
            tasks.append(task)

    _write_jsonl(tasks, Path(args.out))
    print(f"Wrote {len(tasks)} tasks to {args.out}")


if __name__ == "__main__":
    main()
