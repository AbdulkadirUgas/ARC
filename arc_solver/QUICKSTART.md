"""
QUICK START GUIDE
=================

## Step 1: Installation

### Clone/Setup
```bash
cd arc_solver
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

If you get issues with numpy, try:
```bash
pip install --upgrade numpy pydantic
```


## Step 2: Configuration

### Option A: Environment Variables
```bash
export MODEL_ID=deepseek-reasoner
export API_KEY=sk_xxxxxxxxxxxx
export API_BASE_URL=https://api.deepseek.com
```

### Option B: .env File
```bash
cp .env.example .env
# Edit .env with your settings
```

### Option C: Mock Mode (No API Key)
```bash
# Run with --mock flag to test without API key
python main.py task.json --mock
```


## Step 3: Test with Examples

### Generate Example Tasks
```bash
python examples.py
```

This creates: example_task_*.json files

### Run on Simple Task
```bash
python main.py example_task_identity.json
```

Expected output:
```
======================================================================
NEURO-SYMBOLIC ARC SOLVER
======================================================================

[STEP 1] Generating initial hypothesis and code...
[REASONING] Mock perception analysis...
[HYPOTHESIS] Identity transformation...

[ATTEMPT 1] Verifying code...
✓ Verification PASSED on all training examples!

[STEP 5] Running on test input...
✓ Test inference complete!

======================================================================
SOLUTION SUMMARY
======================================================================

✓ TASK SOLVED SUCCESSFULLY!
Retries needed: 0
Output shape: (2, 3)

Final Output:
[[1 1 1]
 [1 1 1]]
```


## Step 4: Run on Your Task

### Prepare Task File
Create `my_task.json`:
```json
{
    "train": [
        {
            "input": [[0, 1, 0], [1, 1, 1], [0, 1, 0]],
            "output": [[0, 2, 0], [2, 2, 2], [0, 2, 0]]
        }
    ],
    "test": [
        {
            "input": [[1, 0, 1], [0, 0, 0], [1, 0, 1]]
        }
    ]
}
```

### Run Solver
```bash
python main.py my_task.json --output solution.json
```

### View Solution
```bash
cat solution.json
```


## Step 5: Use Programmatically

### Python Script
```python
from agent import NeuroSymbolicAgent
import json

# Load task
with open('my_task.json') as f:
    task = json.load(f)

# Create agent
agent = NeuroSymbolicAgent()

# Solve task
solution = agent.solve_task(task)

# Check result
if solution.success:
    print("Task solved!")
    print(f"Output shape: {solution.final_output.shape}")
    print(f"Attempts: {solution.num_retries}")
else:
    print(f"Failed: {solution.error_message}")
```

Save as `solve_my_task.py` and run:
```bash
python solve_my_task.py
```


## Common Issues & Fixes

### 1. "ModuleNotFoundError: No module named 'anthropic'"
```bash
pip install anthropic
```

### 2. "API_KEY not set" Warning
```bash
# Set your API key
export API_KEY=your-key-here
# Or use mock mode
python main.py task.json --mock
```

### 3. Code Execution Timeout
The task is too complex. Try:
- Reduce training examples if possible
- Increase SANDBOX_TIMEOUT in config.py
- Check if your code has infinite loops

### 4. "shape mismatch" Error
Your code transforms to wrong dimensions. The refinement loop will:
1. Show expected vs actual shape
2. Ask LLM to fix shape handling
3. Retry with refined code

### 5. JSON Parse Error
Check that your task.json is valid:
```bash
python -m json.tool my_task.json
```


## Advanced Usage

### Run Tests
```bash
python -m unittest test_sandbox.py -v
```

### Custom Configuration
Edit `config.py`:
```python
@dataclass
class Config:
    MODEL_ID: str = "claude-3-opus"
    MAX_RETRIES: int = 3
    SANDBOX_TIMEOUT: int = 5
    # ... other settings
```

### Batch Processing
```bash
# Process all tasks in tasks/ folder
for f in tasks/*.json; do
    python main.py "$f" --output "solutions/$(basename $f)"
done
```

### Debug Mode
Enable detailed logging in agent.py:
```python
print(f"[DEBUG] Response: {response}")
print(f"[DEBUG] Extracted code: {code[:100]}...")
```


## Performance Tips

### Faster Solutions
1. **Provide good training examples**: More/better examples → faster solution
2. **Simple transformations**: Identity, color swap → faster
3. **Reduce MAX_RETRIES**: Set to 2-3 for quick testing

### Cost Optimization (API)
1. Use cheaper models first (e.g., Claude Haiku)
2. Set MAX_RETRIES = 3 to limit retries
3. Use mock mode for testing/development
4. Cache verified code patterns

### Memory Optimization
1. Normalize grids (convert to int32)
2. Don't load unnecessary data
3. Clear large arrays between tasks

## Next Steps

1. **Read ARCHITECTURE.md** for deep dive into design
2. **Check examples.py** for more example patterns
3. **Modify prompts.py** for domain-specific reasoning
4. **Extend utils.py** with custom grid analysis
5. **Run on real ARC tasks** from https://arcprize.org

## Support & Debugging

### Print Debug Info
```python
from config import config
print(f"Config: {config}")
```

### Trace Execution
```python
from agent import NeuroSymbolicAgent
agent = NeuroSymbolicAgent()
solution = agent.solve_task(task)

# Check details
print(f"Success: {solution.success}")
print(f"Code:\n{solution.final_code}")
print(f"Error: {solution.error_message}")
```

### Validate Code
```python
from sandbox import run_verification
import numpy as np

code = "import numpy as np\ndef transform(grid):\n    return grid"
train_pairs = [{"input": [[1, 2]], "output": [[1, 2]]}]

success, error = run_verification(code, train_pairs)
print(f"Valid: {success}")
if not success:
    print(f"Error: {error}")
```

Happy ARC solving! 🚀
"""
