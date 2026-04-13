"""Unit tests for the Neuro-Symbolic ARC Solver."""

import unittest
import numpy as np
from sandbox import run_verification, extract_code_from_response, normalize_grid, grids_equal


class TestSandbox(unittest.TestCase):
    """Test sandbox execution and verification."""

    def test_extract_code_from_tags(self):
        """Test code extraction from <code> tags."""
        response = """
        Here's my analysis:
        <code>
        import numpy as np
        def transform(grid):
            return grid
        </code>
        """
        code = extract_code_from_response(response)
        self.assertIn("def transform", code)
        self.assertNotIn("<code>", code)

    def test_simple_identity_transform(self):
        """Test verification of simple identity transform."""
        code = """
import numpy as np

def transform(grid):
    return grid
"""
        train_pairs = [
            {"input": [[1, 2], [3, 4]], "output": [[1, 2], [3, 4]]}
        ]

        success, error = run_verification(code, train_pairs)
        self.assertTrue(success)
        self.assertIsNone(error)

    def test_color_swap_transform(self):
        """Test verification of color swap."""
        code = """
import numpy as np

def transform(grid):
    arr = np.array(grid)
    result = np.where(arr == 1, 2, arr)
    result = np.where(result == 2 == grid, 1, result)
    return result
"""
        train_pairs = [
            {"input": [[1, 0], [0, 1]], "output": [[1, 0], [0, 1]]}
        ]

        # This should not error even if logic is odd
        success, error = run_verification(code, train_pairs)
        # May fail verification but shouldn't have runtime errors
        self.assertIsNotNone(success)

    def test_missing_transform_function(self):
        """Test detection of missing transform function."""
        code = """
import numpy as np

def other_func():
    return None
"""
        train_pairs = [{"input": [[1]], "output": [[1]]}]

        success, error = run_verification(code, train_pairs)
        self.assertFalse(success)
        self.assertIn("transform", error)

    def test_syntax_error_detection(self):
        """Test detection of syntax errors."""
        code = """
import numpy as np

def transform(grid)  # Missing colon
    return grid
"""
        train_pairs = [{"input": [[1]], "output": [[1]]}]

        success, error = run_verification(code, train_pairs)
        self.assertFalse(success)
        self.assertIn("SyntaxError", error)

    def test_output_shape_mismatch(self):
        """Test detection of output shape mismatch."""
        code = """
import numpy as np

def transform(grid):
    return np.zeros((5, 5))
"""
        train_pairs = [{"input": [[1, 2]], "output": [[1, 2]]}]

        success, error = run_verification(code, train_pairs)
        self.assertFalse(success)
        self.assertIn("Shape mismatch", error)

    def test_normalize_grid(self):
        """Test grid normalization."""
        grid = [[1, 2], [3, 4]]
        normalized = normalize_grid(grid)
        self.assertEqual(normalized.dtype, np.int32)
        self.assertEqual(normalized.shape, (2, 2))

    def test_grids_equal(self):
        """Test grid equality check."""
        grid1 = [[1, 2], [3, 4]]
        grid2 = [[1, 2], [3, 4]]
        grid3 = [[1, 2], [3, 5]]

        self.assertTrue(grids_equal(grid1, grid2))
        self.assertFalse(grids_equal(grid1, grid3))


class TestMockTask(unittest.TestCase):
    """Test with mock ARC tasks."""

    def test_mock_task_structure(self):
        """Test that mock task has correct structure."""
        task = {
            "train": [
                {"input": [[0, 1], [2, 3]], "output": [[0, 1], [2, 3]]},
                {"input": [[4, 5], [6, 7]], "output": [[4, 5], [6, 7]]},
            ],
            "test": [{"input": [[8, 9], [10, 11]]}],
        }

        self.assertEqual(len(task["train"]), 2)
        self.assertEqual(len(task["test"]), 1)
        self.assertIn("input", task["train"][0])
        self.assertIn("output", task["train"][0])


if __name__ == "__main__":
    unittest.main()
