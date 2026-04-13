"""Main driver for ARC task generation."""
from __future__ import annotations

import argparse
import importlib
import json
import pkgutil
import random
from pathlib import Path
from typing import Any, Dict, List

from validator import validate_task

Task = Dict[str, Any]


def _discover_generators() -> Dict[str, str]:
    generators = {}
    pkg_name = "generators"
    package = importlib.import_module(pkg_name)
    for _, modname, ispkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        if ispkg:
            continue
        generators[modname.split(".")[-1]] = modname
    return generators


def _load_generator(module_path: str):
    module = importlib.import_module(module_path)
    if not hasattr(module, "generate"):
        raise ValueError(f"Generator {module_path} missing generate()")
    return module


def _write_jsonl(tasks: List[Task], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as f:
        for task in tasks:
            f.write(json.dumps(task) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="ARC task generator driver")
    parser.add_argument("--generator", type=str, default="random", help="Generator name or 'random'")
    parser.add_argument("--count", type=int, default=1, help="Number of tasks to generate")
    parser.add_argument("--out", type=str, default="dataset/tasks.jsonl", help="Output JSONL file")
    parser.add_argument("--seed", type=int, default=None, help="Seed for reproducibility")
    parser.add_argument("--validate", action="store_true", help="Run validator checks")
    parser.add_argument("--list", action="store_true", help="List available generators")
    args = parser.parse_args()

    generators = _discover_generators()
    if args.list:
        print("Available generators:")
        for name in sorted(generators.keys()):
            print("-", name)
        return

    if args.generator == "random":
        gen_name = random.choice(list(generators.keys()))
    else:
        gen_name = args.generator

    if gen_name not in generators:
        raise SystemExit(f"Unknown generator: {gen_name}")

    module = _load_generator(generators[gen_name])
    tasks: List[Task] = []

    for i in range(args.count):
        seed = None if args.seed is None else args.seed + i
        task = module.generate(seed=seed)
        task_meta = task.get("meta", {})
        task_meta.update({"generator": gen_name, "seed": seed})
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
