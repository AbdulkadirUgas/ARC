"""Utility functions for the ARC solver."""

import numpy as np
from typing import List, Tuple, Set
from collections import Counter


def get_unique_colors(grid: np.ndarray) -> Set[int]:
    """Get all unique colors in a grid."""
    return set(np.unique(grid).astype(int).tolist())


def get_grid_statistics(grid: np.ndarray) -> dict:
    """Get basic statistics about a grid."""
    return {
        "shape": grid.shape,
        "unique_colors": list(get_unique_colors(grid)),
        "num_unique": len(get_unique_colors(grid)),
        "background_color": int(np.bincount(grid.flatten()).argmax()),
    }


def find_objects(grid: np.ndarray, background: int = 0) -> List[np.ndarray]:
    """
    Find connected components (objects) in a grid.
    Returns list of bounding boxes for each object.
    """
    visited = np.zeros_like(grid, dtype=bool)
    objects = []

    def flood_fill(r, c, color):
        """Flood fill to find connected region."""
        if r < 0 or r >= grid.shape[0] or c < 0 or c >= grid.shape[1]:
            return
        if visited[r, c] or grid[r, c] == background:
            return

        visited[r, c] = True

        flood_fill(r + 1, c, color)
        flood_fill(r - 1, c, color)
        flood_fill(r, c + 1, color)
        flood_fill(r, c - 1, color)

    for r in range(grid.shape[0]):
        for c in range(grid.shape[1]):
            if not visited[r, c] and grid[r, c] != background:
                flood_fill(r, c, grid[r, c])
                objects.append((r, c))  # Representative point

    return objects


def compare_grids(grid1: np.ndarray, grid2: np.ndarray) -> dict:
    """
    Compare two grids and return differences.
    """
    if grid1.shape != grid2.shape:
        return {
            "shape_match": False,
            "shape_1": grid1.shape,
            "shape_2": grid2.shape,
        }

    diff_mask = grid1 != grid2
    num_diffs = np.sum(diff_mask)

    return {
        "shape_match": True,
        "values_match": num_diffs == 0,
        "num_differences": int(num_diffs),
        "difference_locations": np.where(diff_mask),
    }


def describe_transformation(
    input_grid: np.ndarray, output_grid: np.ndarray
) -> str:
    """Generate a human-readable description of a transformation."""
    descriptions = []

    # Shape change
    if input_grid.shape != output_grid.shape:
        descriptions.append(
            f"Shape: {input_grid.shape} → {output_grid.shape}"
        )

    # Color changes
    input_colors = get_unique_colors(input_grid)
    output_colors = get_unique_colors(output_grid)

    new_colors = output_colors - input_colors
    removed_colors = input_colors - output_colors
    kept_colors = input_colors & output_colors

    if new_colors:
        descriptions.append(f"New colors: {new_colors}")
    if removed_colors:
        descriptions.append(f"Removed colors: {removed_colors}")

    return " | ".join(descriptions) if descriptions else "Identity transformation"


if __name__ == "__main__":
    # Example usage
    grid = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]])
    print("Grid statistics:", get_grid_statistics(grid))
    print("Unique colors:", get_unique_colors(grid))
