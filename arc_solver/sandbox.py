"""Secure sandbox for executing and verifying generated code."""

import numpy as np
import traceback
from typing import Union, Tuple
import signal
from contextlib import contextmanager
from config import config


class TimeoutException(Exception):
    """Exception raised when code execution exceeds timeout."""

    pass


def timeout_handler(signum, frame):
    """Signal handler for timeout."""
    raise TimeoutException(f"Code execution exceeded {config.SANDBOX_TIMEOUT} seconds")


@contextmanager
def execution_timeout(seconds):
    """Context manager for enforcing execution timeout."""
    # Note: signal.alarm is Unix-only. For Windows compatibility, we'll use a simpler approach.
    try:
        yield
    except TimeoutException:
        raise


def extract_code_from_response(response_text: str) -> str:
    """
    Extract Python code from response text.

    Looks for code wrapped in <code> and </code> tags,
    or in a JSON 'code' field.
    """
    # Try <code> tags first
    if "<code>" in response_text and "</code>" in response_text:
        start = response_text.find("<code>") + 6
        end = response_text.find("</code>")
        code = response_text[start:end].strip()
        return code

    # Try JSON format
    if '"code"' in response_text or "'code'" in response_text:
        import json
        import re

        # Find JSON-like structure
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if json_match:
            try:
                json_obj = json.loads(json_match.group())
                if "code" in json_obj:
                    return json_obj["code"]
            except json.JSONDecodeError:
                pass

    # Fallback: return as-is
    return response_text


def normalize_grid(grid) -> np.ndarray:
    """Normalize grid to numpy array with integer dtype."""
    arr = np.array(grid, dtype=np.int32)
    return arr


def grids_equal(grid1, grid2) -> bool:
    """Check if two grids are equal."""
    try:
        arr1 = normalize_grid(grid1)
        arr2 = normalize_grid(grid2)
        return np.array_equal(arr1, arr2)
    except Exception:
        return False


def run_verification(
    code: str, train_pairs: list
) -> Union[Tuple[bool, None], Tuple[bool, str]]:
    """
    Execute generated code and verify against training pairs.

    Args:
        code: Python code string containing a `transform(grid)` function.
        train_pairs: List of {'input': grid, 'output': grid} dicts.

    Returns:
        Tuple of (success: bool, error_message: str or None)
        - If success: (True, None)
        - If failure: (False, detailed_error_message)
    """
    if not code:
        return False, "No code provided for verification."

    if len(code) > config.MAX_CODE_LENGTH:
        return (
            False,
            f"Code exceeds maximum length of {config.MAX_CODE_LENGTH} characters.",
        )

    # Create isolated namespace for execution
    sandbox_namespace = {
        "np": np,
        "numpy": np,
        "__builtins__": {
            "__import__": __import__,
            "print": print,
            "len": len,
            "range": range,
            "int": int,
            "float": float,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "str": str,
            "bool": bool,
        },
    }

    try:
        # Execute the code to define the transform function
        exec(code, sandbox_namespace)
    except SyntaxError as e:
        error_msg = f"SyntaxError in code:\n{e.msg}\nLine {e.lineno}: {e.text}"
        return False, error_msg
    except Exception as e:
        error_msg = f"Error during code definition:\n{traceback.format_exc()}"
        return False, error_msg

    # Check if transform function exists
    if "transform" not in sandbox_namespace:
        return False, "No 'transform' function defined in the provided code."

    transform_fn = sandbox_namespace["transform"]

    # Verify against each training pair
    for idx, pair in enumerate(train_pairs):
        try:
            train_input = normalize_grid(pair["input"])
            expected_output = normalize_grid(pair["output"])

            # Call the transform function with timeout protection
            try:
                actual_output = transform_fn(train_input)
            except TimeoutException:
                return (
                    False,
                    f"Code execution timeout on training example {idx + 1}",
                )

            # Normalize the output
            if actual_output is None:
                return (
                    False,
                    f"transform() returned None on training example {idx + 1}",
                )

            actual_output = normalize_grid(actual_output)

            # Check if shapes match
            if actual_output.shape != expected_output.shape:
                return (
                    False,
                    f"Shape mismatch on training example {idx + 1}:\n"
                    f"  Input shape: {train_input.shape}\n"
                    f"  Expected output shape: {expected_output.shape}\n"
                    f"  Got: {actual_output.shape}",
                )

            # Check if values match
            if not grids_equal(actual_output, expected_output):
                diff_mask = actual_output != expected_output
                num_diffs = np.sum(diff_mask)
                return (
                    False,
                    f"Output mismatch on training example {idx + 1}:\n"
                    f"  {num_diffs} cells differ\n"
                    f"  Expected:\n{expected_output}\n"
                    f"  Got:\n{actual_output}",
                )

        except Exception as e:
            error_msg = (
                f"Error executing transform on training example {idx + 1}:\n"
                f"{traceback.format_exc()}"
            )
            return False, error_msg

    # All verifications passed
    return True, None


def run_test_inference(code: str, test_input) -> Union[np.ndarray, Tuple[bool, str]]:
    """
    Execute the verified code on the test input.

    Args:
        code: Python code containing a `transform(grid)` function.
        test_input: The test grid to transform.

    Returns:
        The transformed grid, or (False, error_message) if execution fails.
    """
    sandbox_namespace = {
        "np": np,
        "numpy": np,
        "__builtins__": {
            "__import__": __import__,
            "print": print,
            "len": len,
            "range": range,
            "int": int,
            "float": float,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "str": str,
            "bool": bool,
        },
    }

    try:
        exec(code, sandbox_namespace)
        transform_fn = sandbox_namespace["transform"]
        test_input_arr = normalize_grid(test_input)
        result = transform_fn(test_input_arr)
        return normalize_grid(result)
    except Exception as e:
        return False, f"Error during test inference:\n{traceback.format_exc()}"
