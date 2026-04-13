"""
NEURO-SYMBOLIC ARC SOLVER
Architecture & Design Document
==============================

## 1. SYSTEM OVERVIEW

The Neuro-Symbolic ARC Solver is a production-ready Python system designed to tackle
the ARC-AGI (Abstract Reasoning Challenge) through a structured reasoning loop:

    INPUT TASK
        ↓
    [PERCEIVE] - Analyze grids, identify patterns
        ↓
    [HYPOTHESIZE] - Generate transformation rules
        ↓
    [CODE] - Write Python function
        ↓
    [VERIFY] - Test on training examples
        ├─ SUCCESS → [SOLVE] Apply to test input
        └─ FAILURE → [REFINE] & retry (max 5 times)
        ↓
    OUTPUT SOLUTION


## 2. COMPONENT ARCHITECTURE

### 2.1 Configuration Layer (config.py)
- Centralized settings management
- Environment variable support
- Dataclass-based configuration
- Runtime validation

Key Settings:
- MODEL_ID: Which LLM to use
- MAX_RETRIES: Maximum refinement attempts
- SANDBOX_TIMEOUT: Code execution timeout
- MAX_CODE_LENGTH: Safety limit on generated code

### 2.2 Prompt Engineering (prompts.py)
- SYSTEM_PROMPT: Defines agent role and protocols
- REASONING_PROMPT_TEMPLATE: Initial task analysis
- REFINEMENT_PROMPT_TEMPLATE: Error recovery guidance
- Structured output requests (JSON format)

Design Principles:
- Clear protocols (NO MEMORIZATION, SPATIAL AWARENESS)
- Step-by-step reasoning pipeline
- Explicit code block markers (<code> tags)
- JSON response structure for easy parsing

### 2.3 Sandbox Execution (sandbox.py)
- Safe code execution with restricted builtins
- Timeout protection
- Automatic error detection and reporting
- Grid normalization and comparison

Key Functions:
- run_verification(code, train_pairs) → (bool, error_msg)
- run_test_inference(code, test_input) → grid or error
- extract_code_from_response(response_text) → code string

Safety Features:
- Limited namespace with only essential builtins
- Numpy and basic math functions allowed
- String formatting and collection operations
- Exception handling with detailed tracebacks

### 2.4 Agent Logic (agent.py)
- NeuroSymbolicAgent class: Main orchestrator
- Implements the reasoning loop
- Handles LLM integration
- Manages retry logic and refinement

Workflow:
1. Parse task into training and test pairs
2. Call LLM for initial reasoning → code
3. Verify code against training examples
4. If success: Run on test input, return solution
5. If failure: Extract error, request refinement, retry
6. Track attempts and provide detailed feedback

### 2.5 CLI Interface (main.py)
- Command-line entry point
- Argument parsing
- Task loading and validation
- Solution saving and reporting

Usage:
```
python main.py task.json [--output solution.json] [--mock]
```

### 2.6 Utilities (utils.py)
- Grid analysis functions
- Pattern recognition helpers
- Transformation description generation
- Statistics and comparison tools

Available Functions:
- get_unique_colors(grid) → set
- get_grid_statistics(grid) → dict
- find_objects(grid) → list
- compare_grids(grid1, grid2) → dict
- describe_transformation(input, output) → str

### 2.7 Examples (examples.py)
- Pre-built example tasks for testing
- Task file generation
- Reference implementations

Included Examples:
- TASK_IDENTITY: Trivial passthrough
- TASK_COLOR_SWAP: Swap one color for another
- TASK_ROW_DOUBLE: Double each row
- TASK_FILL: Fill background with color


## 3. DATA FLOW

### 3.1 Input Format
```
Task JSON Structure:
{
    "train": [
        {
            "input": [[0, 1, 0], [1, 1, 1], [0, 1, 0]],
            "output": [[0, 2, 0], [2, 2, 2], [0, 2, 0]]
        },
        ... more examples ...
    ],
    "test": [
        {
            "input": [[1, 0, 1], [0, 1, 0], [1, 0, 1]]
        }
    ]
}
```

### 3.2 Internal Representation
```
Training Pairs:
[
    {"input": np.array([...]), "output": np.array([...])},
    ...
]

Test Cases:
[
    {"input": np.array([...])}
]
```

### 3.3 Code Execution Flow
```
Generated Code String
    ↓
extract_code_from_response()
    ↓
exec() in restricted namespace
    ↓
transform() function extracted
    ↓
Executed on each training pair
    ↓
Output compared to expected
    ↓
(Success/Failure, Error Details)
```

### 3.4 Output Format
```
TaskSolution:
- success: bool
- final_code: str (Python function)
- final_output: np.ndarray (test grid solution)
- num_retries: int
- error_message: str or None

JSON Output:
{
    "success": true,
    "num_retries": 1,
    "error_message": null,
    "final_code": "import numpy as np\ndef transform(grid):\n...",
    "final_output": [[...]]
}
```


## 4. ERROR HANDLING STRATEGY

### 4.1 Code Generation Errors
- **SyntaxError**: Caught during exec(), reported to LLM
- **NameError**: Undefined variables, reported with line context
- **TypeError**: Wrong function signatures, detected and reported
- **ImportError**: Missing imports in generated code, handled gracefully

### 4.2 Verification Errors
- **Shape Mismatch**: Expected shape != actual shape
  - Recovery: Request shape-aware refinement
- **Value Mismatch**: Values differ, detailed diff provided
  - Recovery: Show specific cell differences
- **Runtime Error**: Exception during execution
  - Recovery: Full traceback provided to LLM

### 4.3 Timeout Handling
- Code execution timeout: 10 seconds default
- LLM call timeout: 30 seconds default
- Graceful degradation with error messages

### 4.4 Retry Logic
```
for attempt in range(MAX_RETRIES):
    code = generate_or_refine_code()
    success, error = verify(code)
    if success:
        return solve(code)
    else:
        # Create refinement prompt with error
        code = refine_code(error)
        # Loop continues
```


## 5. LLM INTEGRATION POINTS

### 5.1 Initial Reasoning
Input: Training examples + test input
Output: JSON with perception, hypothesis, code

Structured as:
```json
{
    "perception": "Description of patterns",
    "hypothesis_1": "First possible rule",
    "hypothesis_2": "Second possible rule",
    "hypothesis_3": "Third possible rule",
    "chosen_hypothesis": "Most likely rule",
    "code": "Python function implementation",
    "verification_logic": "Why this should work"
}
```

### 5.2 Refinement Prompting
Input: Previous code + error message + failed example
Output: Refined code with explanation

Includes:
- Original hypothesis and code
- Specific error message
- Example where it failed
- Expected vs actual output
- Request for improved code

### 5.3 Supported LLM Providers
Currently Implemented:
- Anthropic Claude (API)
- Mock (for testing)

Easily Extensible To:
- OpenAI GPT-4
- DeepSeek Reasoner
- Ollama (local models)
- LM Studio
- Custom inference endpoints


## 6. SECURITY CONSIDERATIONS

### 6.1 Code Injection Prevention
- exec() used with restricted namespace
- Only safe builtins provided
- No file I/O, network, or system calls
- Timeout protection against infinite loops

### 6.2 Prompt Injection Prevention
- Structured prompts with clear delimiters
- JSON parsing for code extraction
- Validation of code before execution
- Error messages sanitized before display

### 6.3 Resource Limits
- Code length limit: 2000 characters
- Execution timeout: 10 seconds
- Retry limit: 5 attempts
- Memory: Bounded by numpy array sizes


## 7. TESTING STRATEGY

### 7.1 Unit Tests (test_sandbox.py)
- Code extraction tests
- Verification logic tests
- Error detection tests
- Grid normalization tests

### 7.2 Integration Tests
- Full task solving pipeline
- Error recovery workflow
- JSON I/O validation

### 7.3 Example Tasks
- Identity transformation (trivial)
- Color swap (simple rule)
- Row doubling (shape change)
- Background fill (pattern discovery)

### 7.4 Edge Cases
- Empty grids
- Single-pixel grids
- Asymmetric transformations
- Multiple color spaces


## 8. PERFORMANCE CHARACTERISTICS

### 8.1 Per-Task Performance
Typical Simple Task (2-3 examples):
- Initial reasoning: 5-15 seconds
- First verification: <1 second
- Total: 5-20 seconds → Solution

Typical Medium Task (4-6 examples):
- Initial reasoning + refinement: 10-30 seconds
- 2-3 verification cycles
- Total: 20-60 seconds → Solution

Complex Task (7+ examples):
- Multiple refinement cycles
- May hit max retries
- Total: 30-120 seconds → Failure or Solution

### 8.2 Memory Usage
- Depends on grid size
- Typical: <100 MB for task data
- Sandbox overhead: ~10 MB
- Total: 50-150 MB per task

### 8.3 Scalability
- Linear in training example count
- Quadratic in retry count (due to LLM calls)
- Can parallelize multiple task solving


## 9. EXTENSIBILITY POINTS

### 9.1 Custom Prompt Engineering
Edit `prompts.py`:
- Modify SYSTEM_PROMPT for different reasoning styles
- Change REASONING_PROMPT_TEMPLATE for different input format
- Add domain-specific guidance in REFINEMENT_PROMPT_TEMPLATE

### 9.2 Custom LLM Backends
In `agent.py`, replace `_init_llm()` and `_call_llm()`:
```python
def _init_llm(self):
    # Initialize your custom LLM

def _call_llm(self, system_prompt, user_message):
    # Call your LLM API
    # Return response string
```

### 9.3 Custom Verification Logic
In `sandbox.py`, modify:
- `run_verification()`: Change equality criteria
- `normalize_grid()`: Add preprocessing
- `grids_equal()`: Implement fuzzy matching

### 9.4 Custom Grid Analysis
In `utils.py`, add:
- Domain-specific pattern detectors
- Rule-based transformations
- Symbolic reasoning layers


## 10. DEPLOYMENT CONSIDERATIONS

### 10.1 Requirements
- Python 3.10+
- numpy, pydantic, tenacity
- LLM API key (Claude, DeepSeek, etc.)
- ~100-200 MB disk space

### 10.2 Production Checklist
- [ ] Set API_KEY environment variable
- [ ] Configure MODEL_ID for your LLM
- [ ] Test with example tasks first
- [ ] Set MAX_RETRIES based on cost/time budget
- [ ] Monitor API usage and costs
- [ ] Implement result logging
- [ ] Add task-level error handling
- [ ] Set up monitoring and alerting

### 10.3 Docker Deployment
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV API_KEY=${API_KEY}
ENV MODEL_ID=deepseek-reasoner
CMD ["python", "main.py", "task.json"]
```

### 10.4 Batch Processing
```python
import glob
from agent import NeuroSymbolicAgent

agent = NeuroSymbolicAgent()
for task_file in glob.glob("tasks/*.json"):
    task = load_task_file(task_file)
    solution = agent.solve_task(task)
    save_solution(solution, f"solutions/{task_file.stem}.json")
```


## 11. FUTURE ENHANCEMENTS

### 11.1 Planned Features
- [ ] Multi-test case support
- [ ] Visual grid rendering (ASCII/PNG)
- [ ] Batch task processing
- [ ] Result analytics dashboard
- [ ] Few-shot learning across tasks
- [ ] Hybrid symbolic reasoning layer
- [ ] Model ensemble voting

### 11.2 Research Directions
- Neuro-symbolic integration with graph neural networks
- Abstract rule discovery using formal logic
- Multi-modal reasoning (images + text descriptions)
- Meta-learning across task families
- Compositional reasoning (breaking tasks into subtasks)

### 11.3 Performance Optimization
- Caching of verified code patterns
- Parallel verification of multiple hypotheses
- Streaming LLM responses
- Incremental refinement feedback


## 12. REFERENCES & RESOURCES

- ARC-AGI Challenge: https://arcprize.org
- ARC Dataset: https://github.com/fchollet/ARC
- Neuro-Symbolic AI: https://en.wikipedia.org/wiki/Neurosymbolic_AI
- DeepSeek API Docs: https://api.deepseek.com/docs
- Anthropic Claude API: https://docs.anthropic.com
"""

# Architecture version
__version__ = "1.0.0"
__last_updated__ = "2024"
