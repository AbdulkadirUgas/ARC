"""Main CLI entry point for the Neuro-Symbolic ARC Solver."""

import json
import sys
import argparse
import asyncio
from pathlib import Path
from datetime import datetime
import numpy as np

from agent import NeuroSymbolicAgent


def load_task_fileOld(filepath: str) -> dict:
    """Load and parse a task JSON file."""
    try:
        with open(filepath, "r") as f:
            for i, line in enumerate(f):
                if line.strip():
                    try:
                        task = json.loads(line)
                        return task
                    except json.JSONDecodeError as e:
                        print(f"Error: Invalid JSON on line {i+1}: {e}")
                        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: Task file not found: {filepath}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in task file: {e}")
        sys.exit(1)


def load_task_file(filepath: str) -> dict:
    """Load and parse a task JSON file."""
    try:
        tasks = []
        if filepath.endswith(".json"):
            with open(filepath, "r") as f:
                tasks = json.load(f)
            return tasks
        elif filepath.endswith(".jsonl"):
            with open(filepath, "r") as f:
                for line in f:
                    tasks.append(json.loads(line.strip()))
            return tasks
    except FileNotFoundError:
        print(f"Error: Task file not found: {filepath}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in task file: {e}")
        sys.exit(1)




def format_grid_for_output(grid: np.ndarray) -> list:
    """Convert numpy array to nested list for JSON serialization."""
    return grid.astype(int).tolist()


def save_solution(solution_dict: dict, output_path: str):
    """Save solution to JSON file."""
    try:
        with open(output_path, "w") as f:
            json.dump(solution_dict, f, indent=2)
        print(f"\n✓ Solution saved to: {output_path}")
    except Exception as e:
        print(f"Error saving solution: {e}")


def print_solution_summary(solution):
    """Print a summary of the solution."""
    print("\n" + "=" * 70)
    print("SOLUTION SUMMARY")
    print("=" * 70)

    if solution.success:
        print("✓ TASK SOLVED SUCCESSFULLY!")
        print(f"Retries needed: {solution.num_retries}")
        print(f"Output shape: {solution.final_output.shape}")
        print(f"\nFinal Output:\n{solution.final_output}")
        print(f"\nFinal Code:\n{solution.final_code}")
    else:
        print("✗ TASK FAILED")
        print(f"Retries attempted: {solution.num_retries}")
        print(f"Error: {solution.error_message}")
        if solution.final_code:
            print(f"\nLast attempted code:\n{solution.final_code}")


async def main():
    """Main entry point."""
    start_time = datetime.now()
    parser = argparse.ArgumentParser(
        description="Neuro-Symbolic ARC-AGI Solver",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py task.json
  python main.py task.json --output solution.json
  python main.py task.json --mock
        """,
    )

    parser.add_argument("task_file", help="Path to ARC task JSON file")
    parser.add_argument(
        "-o",
        "--output",
        help="Output file for the solution (optional)",
        default=None,
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock LLM (for testing)",
    )

    args = parser.parse_args()

    # Load task
    print("Loading task...")
    tasks = [load_task_file(args.task_file)]

    # Initialize agent
    print("Initializing Neuro-Symbolic Agent...")
    agent = NeuroSymbolicAgent()

    solutions = []
    # Solve task
    print("Starting task resolution...")
    # solution =  await agent.solve_task(task)
    for task in tasks:
        solution = await agent.solve_task(task)
        solutions.append(solution)
        

    # Print summary
    # print_solution_summary(solution)
    solution = solutions[-1]  # Print summary for the last solution
    for i, solution in enumerate(solutions):
        print(f"\n=== Solution Summary for Task {i+1} ===")
        print_solution_summary(solution)

    # Save if output path specified
    if args.output:
        solution_dict = {
            "success": solution.success,
            "num_retries": solution.num_retries,
            "error_message": solution.error_message,
            "final_code": solution.final_code,
            "final_output": (
                format_grid_for_output(solution.final_output)
                if solution.final_output is not None
                else None
            ),
        }
        save_solution(solution_dict, args.output)
    end_time = datetime.now()
    duration = end_time - start_time
    print(f"\nTotal execution time: {duration}")
    # Exit with appropriate code
    sys.exit(0 if solution.success else 1)


if __name__ == "__main__":
    asyncio.run(main())
