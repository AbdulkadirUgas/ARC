"""Example ARC-like tasks for testing and demonstration."""

import json

# Simple color swap task
TASK_COLOR_SWAP = {
    "train": [
        {
            "input": [[0, 1, 0], [1, 0, 1], [0, 1, 0]],
            "output": [[0, 2, 0], [2, 0, 2], [0, 2, 0]],
        },
        {
            "input": [[1, 1, 1], [1, 0, 1], [1, 1, 1]],
            "output": [[2, 2, 2], [2, 0, 2], [2, 2, 2]],
        },
    ],
    "test": [
        {
            "input": [[0, 1, 1], [1, 1, 0], [0, 0, 1]],
        }
    ],
}

# Simple identity task (should pass trivially)
TASK_IDENTITY = {
    "train": [
        {
            "input": [[1, 2, 3], [4, 5, 6]],
            "output": [[1, 2, 3], [4, 5, 6]],
        },
        {
            "input": [[7, 8], [9, 0]],
            "output": [[7, 8], [9, 0]],
        },
    ],
    "test": [
        {
            "input": [[1, 1, 1], [1, 1, 1]],
        }
    ],
}

# Simple row doubling task
TASK_ROW_DOUBLE = {
    "train": [
        {
            "input": [[1, 2], [3, 4]],
            "output": [[1, 2], [1, 2], [3, 4], [3, 4]],
        },
        {
            "input": [[5, 6, 7]],
            "output": [[5, 6, 7], [5, 6, 7]],
        },
    ],
    "test": [
        {
            "input": [[8, 9]],
        }
    ],
}

# Simple fill task (fill background with a specific color)
TASK_FILL = {
    "train": [
        {
            "input": [[0, 0, 0], [0, 5, 0], [0, 0, 0]],
            "output": [[1, 1, 1], [1, 5, 1], [1, 1, 1]],
        },
        {
            "input": [[0, 0], [0, 7]],
            "output": [[1, 1], [1, 7]],
        },
    ],
    "test": [
        {
            "input": [[0, 0, 0], [0, 0, 0], [0, 3, 0]],
        }
    ],
}


def save_example_task(task_dict: dict, filename: str):
    """Save an example task to a JSON file."""
    with open(filename, "w") as f:
        json.dump(task_dict, f, indent=2)
    print(f"Saved task to {filename}")


if __name__ == "__main__":
    # Create example task files
    save_example_task(TASK_IDENTITY, "examples/example_task_identity.json")
    save_example_task(TASK_COLOR_SWAP, "examples/example_task_color_swap.json")
    save_example_task(TASK_ROW_DOUBLE, "examples/example_task_row_double.json")
    save_example_task(TASK_FILL, "examples/example_task_fill.json")
