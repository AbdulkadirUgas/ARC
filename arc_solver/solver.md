# MISSION: GENERATE "NEURO-SYMBOLIC ARC SOLVER" PROJECT

**Role:** You are a Principal AI Architect.
**Objective:** Generate a complete, production-ready Python project structure for a "Neuro-Symbolic Agent" designed to solve the ARC-AGI challenge.
**Tech Stack:** Python 3.10+, `numpy`, `pydantic` (for structured output), `tenacity` (for retries), and `anthropic` (or `openai` compatible client).

## 1. ARCHITECTURE & LOGIC
The system must implement a **"Reasoning -> Coding -> Verification" Loop**:
1.  **Perceive:** The agent analyzes the Input/Output grids.
2.  **Hypothesize:** It generates a natural language hypothesis (e.g., "Move blue objects down").
3.  **Code:** It writes a Python function `transform(grid) -> grid` representing that hypothesis.
4.  **Verify (CRITICAL):** The system *executes* this code on the Training Examples.
    * If `transform(train_input) == train_output` for ALL examples, the hypothesis is **CONFIRMED**.
    * If it fails, the agent receives the error/diff and must **REFINE** the code (Loop back to Step 3).
5.  **Solve:** Once confirmed, the code is run on the *Test Input* to generate the final submission.

## 2. FILE STRUCTURE TO GENERATE
Please generate the full code for the following files:

### `config.py`
* Settings for Model ID (Default: `claude-3-5-sonnet-latest`).
* Max retries (Default: 5).

### `prompts.py`
* Must contain the `SYSTEM_PROMPT` variable.
* **INSERT THE FOLLOWING TEXT EXACTLY INTO `SYSTEM_PROMPT`:**
    """
    ### SYSTEM ROLE: ARC-AGI REASONING ENGINE ###
    You are an expert Neuro-Symbolic Reasoning Agent. Your goal is to **discover, verify, and execute** the abstract rule governing a transformation.

    ### CORE PROTOCOLS:
    1.  **NO MEMORIZATION:** Treat every task as a novel universe.
    2.  **SPATIAL AWARENESS:** Understand that the input is a 2D grid. "Down" is a coordinate shift (+1, 0).
    3.  **TEST-TIME ADAPTATION:** You must formulate a hypothesis based on the examples and VERIFY it before predicting.

    ### REASONING PIPELINE:
    **STEP 1: PERCEPTION**
    * List objects, background color, symmetries, and recurring shapes.
    **STEP 2: HYPOTHESIS GENERATION**
    * Propose 3 distinct transformation rules.
    **STEP 3: VERIFICATION**
    * Write a Python function `transform(grid)` to simulate your best hypothesis.
    * The system will run this code. If it fails on training examples, you must debug it.
    **STEP 4: EXECUTION**
    * Once the code is verified, applying it to the TEST INPUT is trivial.
    """

### `sandbox.py`
* A secure code execution environment.
* Function `run_verification(code: str, train_pairs: list) -> bool`.
* It should use `exec()` (with basic safety wrappers) to run the agent's generated `transform` function on the input grids and compare the result to the output grids.
* Return `True` if perfect match, else return the `Diff` or `Error Message`.

### `agent.py`
* Class `NeuroSymbolicAgent`.
* Method `solve_task(task_json)`.
* Implements the loop:
    * Call LLM with Task -> Get Code.
    * Call `sandbox.run_verification(code)`.
    * If Success -> Run on Test -> Return Result.
    * If Fail -> Feed error back to LLM -> Retry (up to `MAX_RETRIES`).

### `main.py`
* CLI entry point.
* Load a JSON task file.
* Initialize Agent.
* Print the final result.

## 3. SPECIAL INSTRUCTIONS
* **Structured Output:** Use Pydantic or JSON mode to ensure the LLM returns the "Code" in a specific block that is easy to extract (e.g., inside `<code>` tags or a JSON field).
* **Error Handling:** If the LLM produces invalid Python syntax, the `sandbox` must catch it and return the traceback so the Agent can fix it.

**GENERATE THE FULL PROJECT CODE NOW.**