"""
Neuro-Symbolic ARC Solver
========================

A production-ready Python system for solving ARC-AGI (Abstract Reasoning Challenge) 
tasks using a Reasoning → Coding → Verification loop.

## Quick Start

### 1. Installation

```bash
pip install -r requirements.txt
```

### 2. Configuration

Set your LLM API credentials:

```bash
export MODEL_ID=deepseek-reasoner
export API_KEY=your-api-key-here
```

Or create a `.env` file:

```
MODEL_ID=deepseek-reasoner
API_KEY=your-api-key-here
API_BASE_URL=https://api.deepseek.com
```

### Local LLM Configuration

To use a local model (e.g. Qwen via vLLM) instead of a cloud API, add the following to your environment or `.env`:

```bash
export USE_LOCAL_LLM=True
export LOCAL_LLM_BASE_URL="http://203.227.160.81:8001/v1"
export LOCAL_LLM_MODEL="Qwen/Qwen3-14B"
export LOCAL_LLM_API_KEY=EMPTY  # optional
```

When `USE_LOCAL_LLM` is true, the service will POST the concatenated system/user prompt to `LOCAL_LLM_BASE_URL` and ignore `MODEL_ID`/`API_KEY` values.


### 3. Prepare a Task

Create a JSON file with your ARC task (see `example_task_*.json`):

```json
{
    "train": [
        {
            "input": [[...], [...], ...],
            "output": [[...], [...], ...]
        }
    ],
    "test": [
        {
            "input": [[...], [...], ...]
        }
    ]
}
```

### 4. Run the Solver

```bash
python main.py your_task.json --output solution.json
```

## Architecture

### Core Components

1. **config.py** - Configuration and settings
2. **prompts.py** - System prompts and prompt templates
3. **sandbox.py** - Secure code execution and verification
4. **agent.py** - NeuroSymbolicAgent main class
5. **main.py** - CLI entry point
6. **examples.py** - Example tasks for testing

### Reasoning Loop

```
┌─────────────────────────────────────┐
│ 1. PERCEIVE (Analyze I/O grids)     │
├─────────────────────────────────────┤
│ 2. HYPOTHESIZE (Natural language)   │
├─────────────────────────────────────┤
│ 3. CODE (Write transform function)  │
├─────────────────────────────────────┤
│ 4. VERIFY (Execute on train pairs)  │
│    Success? → Go to Step 5          │
│    Failure? → Refine (back to 3)    │
├─────────────────────────────────────┤
│ 5. SOLVE (Run on test input)        │
└─────────────────────────────────────┘
```

## Key Features

- ✓ **Structured Reasoning**: LLM generates both hypothesis and code
- ✓ **Automatic Verification**: Code is tested on training examples before use
- ✓ **Error Recovery**: Failed code is automatically refined and retried
- ✓ **Safe Execution**: Sandbox with timeout protection and restricted builtins
- ✓ **Production Ready**: Proper error handling, logging, and JSON I/O
- ✓ **Extensible Design**: Easy to integrate with different LLMs

## Usage Examples

### Basic Usage

```bash
python main.py task.json
```

### With Output File

```bash
python main.py task.json --output solution.json
```

### Using Mock LLM (for testing)

```bash
python main.py task.json --mock
```

### Programmatic Usage

```python
from agent import NeuroSymbolicAgent
import json

# Load task
with open('task.json') as f:
    task = json.load(f)

# Solve
agent = NeuroSymbolicAgent()
solution = agent.solve_task(task)

print(f"Success: {solution.success}")
print(f"Output shape: {solution.final_output.shape}")
```

## Testing

```bash
# Run unit tests
python -m unittest test_sandbox.py

# Generate example tasks
python examples.py

# Test with an example
python main.py example_task_identity.json
```

## Configuration

Edit `config.py` to customize:

- `MODEL_ID`: LLM to use (deepseek-reasoner, claude-3-opus, etc.)
- `MAX_RETRIES`: Max refinement attempts (default: 5)
- `TIMEOUT_SECONDS`: LLM call timeout
- `SANDBOX_TIMEOUT`: Code execution timeout
- `TEMPERATURE`: LLM temperature for reasoning

## API Integration

Currently supports:
- Anthropic Claude (with API key)
- Mock mode (for testing without API)

Easy to extend for:
- OpenAI GPT-4
- DeepSeek API
- Local LLMs (Ollama, LM Studio)
- Custom inference endpoints

## Error Handling

The system gracefully handles:

- **SyntaxError** in generated code
- **Shape mismatches** between expected and actual output
- **Value mismatches** with detailed diffs
- **Timeout** on long-running code
- **API failures** with fallback to mock mode
- **Invalid JSON** responses from LLM

## Performance

Typical task solving:
- Simple tasks (2-3 training examples): 1-2 attempts
- Medium tasks (3-5 examples): 2-4 attempts
- Complex tasks: May hit max retries

Each attempt includes:
- LLM reasoning: ~5-20 seconds
- Code verification: <1 second per training example
- Total per attempt: ~10-30 seconds

## Extending the Agent

### Custom Prompts

Edit `prompts.py` to modify:
- `SYSTEM_PROMPT`: Agent's role and capabilities
- `REASONING_PROMPT_TEMPLATE`: Initial reasoning
- `REFINEMENT_PROMPT_TEMPLATE`: Error recovery

### Custom LLM Integration

In `agent.py`, modify `_init_llm()` and `_call_llm()` to integrate your LLM:

```python
def _call_llm(self, system_prompt, user_message):
    # Your custom LLM call here
    response = your_llm_api(system_prompt, user_message)
    return response
```

### Custom Verification Logic

In `sandbox.py`, modify `run_verification()` to add:
- Different equality criteria
- Partial credit for near-misses
- Symbolic reasoning checks

## Limitations

- Currently solves 1 test case per task
- Requires explicit train/test split
- Limited to grid-based transformations
- No multi-modal reasoning (images, text)

## Future Improvements

- [ ] Multi-test case support
- [ ] Visual grid rendering
- [ ] Few-shot learning across tasks
- [ ] Symbolic reasoning with formal logic
- [ ] Hybrid approaches (neural + symbolic)
- [ ] Streaming output for long tasks

## License

MIT License - See LICENSE file

## References

- ARC-AGI Challenge: https://arcprize.org
- ARC Dataset: https://github.com/fchollet/ARC
- Neuro-Symbolic AI: https://en.wikipedia.org/wiki/Neurosymbolic_AI
"""

__version__ = "1.0.0"
__author__ = "Principal AI Architect"
__description__ = "Neuro-Symbolic Agent for ARC-AGI Challenge"
