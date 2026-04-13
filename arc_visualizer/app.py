import json
import os
from itertools import islice
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Standard ARC Color Map
COLORS = {
    0: '#000000', 1: '#0074D9', 2: '#FF4136', 3: '#2ECC40', 4: '#FFDC00',
    5: '#AAAAAA', 6: '#F012BE', 7: '#FF851B', 8: '#7FDBFF', 9: '#870C25'
}

DATA_FILE = os.path.join(os.path.dirname(__file__), 'new_dataset.jsonl')
CONCEPTS_FILE = os.path.join(os.path.dirname(__file__), 'concepts.json')


def load_dotenv(path=None):
    """Lightweight .env loader: read KEY=VALUE lines into os.environ.
    Does not require python-dotenv so it's safe for minimal setups.
    """
    if path is None:
        path = os.path.join(os.path.dirname(__file__), '..', '.env')
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' not in line:
                        continue
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    # don't overwrite existing env vars
                    if key not in os.environ:
                        os.environ[key] = val
    except Exception:
        # Fail silently; .env is optional
        pass


# Load .env early so the app can pick up CONCEPT_REQUIRED / REQUIRED_CONCEPT
load_dotenv()

# If set to 'true' (case-insensitive), the app will force a concept filter
CONCEPT_REQUIRED = os.environ.get('CONCEPT_REQUIRED', 'false').lower() == 'true'
REQUIRED_CONCEPT = os.environ.get('REQUIRED_CONCEPT') or os.environ.get('DEFAULT_CONCEPT')

def load_concepts():
    """Load the pre-scanned concepts list."""
    if os.path.exists(CONCEPTS_FILE):
        with open(CONCEPTS_FILE, 'r') as f:
            return json.load(f)
    return {}

def task_generator(filter_concept=None):
    """
    Generator that yields tasks one by one.
    If filter_concept is set, it skips tasks that don't match.
    """
    if not os.path.exists(DATA_FILE):
        return

    with open(DATA_FILE, 'r') as f:
        abs_id = 0
        for line in f:
            if not line.strip():
                continue

            # try to parse every valid JSON line to increment absolute id
            try:
                task = json.loads(line)
            except json.JSONDecodeError:
                continue

            abs_id += 1

            # If filtering, check concept quickly in raw line (fast path)
            if filter_concept and filter_concept not in line:
                # still incremented abs_id for this parsed task
                continue

            # Strict check after parse
            if filter_concept:
                task_concept = task.get('meta', {}).get('concept')
                if task_concept != filter_concept:
                    continue

            # yield both task and its absolute 1-based ID
            yield task, abs_id

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    selected_concept = request.args.get('concept')

    # If the deployment requires a concept filter, apply the required concept
    # when the user hasn't explicitly selected one.
    if CONCEPT_REQUIRED and not selected_concept:
        selected_concept = REQUIRED_CONCEPT
    
    # Load available concepts for the dropdown
    concepts_counts = load_concepts()
    
    # Calculate skip amount
    start_index = (page - 1) * per_page
    print(f"Serving page {page} (items {start_index} to {start_index + per_page - 1}) with filter concept='{selected_concept}'")
    
    # Create the filtered generator
    gen = task_generator(selected_concept)
    
    # Skip to the requested page
    # NOTE: slicing a filtered generator consumes the file up to that point.
    # Deep pagination on filtered results will be slower.
    page_tasks = list(islice(gen, start_index, start_index + per_page))
    
    return render_template(
        'index.html', 
        tasks=page_tasks, 
        colors=COLORS,
        page=page,
        per_page=per_page,
        selected_concept=selected_concept,
        start_index=start_index,
        concepts=concepts_counts,
        has_next=len(page_tasks) == per_page
    )


def get_task_by_filtered_index(filter_concept, desired_one_based_index):
    """Return the task at the given 1-based index within the filtered sequence.
    If not found, return None.
    """
    if not os.path.exists(DATA_FILE):
        return None
    # Compatibility helper: find the Nth task in the filtered sequence
    if not os.path.exists(DATA_FILE):
        return None

    idx = 0
    with open(DATA_FILE, 'r') as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            try:
                task = json.loads(line)
            except json.JSONDecodeError:
                continue

            # strict check
            if filter_concept:
                task_concept = task.get('meta', {}).get('concept')
                if task_concept != filter_concept:
                    continue

            idx += 1
            if idx == desired_one_based_index:
                return task

    return None


def get_task_by_id(abs_id):
    """Return the task for the given absolute 1-based ID (parsed JSON lines)."""
    if not os.path.exists(DATA_FILE) or not isinstance(abs_id, int) or abs_id < 1:
        return None

    idx = 0
    with open(DATA_FILE, 'r') as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                task = json.loads(line)
            except json.JSONDecodeError:
                continue

            idx += 1
            if idx == abs_id:
                return task

    return None


@app.route('/task', methods=['GET', 'POST'])
def task_detail():
    # Support lookup by absolute id (`id` query param) or filtered index `n`.
    abs_id = request.args.get('id', type=int)
    n = request.args.get('n', type=int)

    selected_concept = request.args.get('concept')

    task = None
    task_id = None
    if abs_id and abs_id > 0:
        task = get_task_by_id(abs_id)
        task_id = abs_id
    elif n and n > 0:
        task = get_task_by_filtered_index(selected_concept, n)
        task_id = None
    else:
        return "Missing task id (use ?id=<number>) or filtered index 'n'", 400

    if task is None:
        return "Task not found", 404

    # Default: show first test pair
    test_index = request.values.get('test_index', 0, type=int)
    test_index = max(0, test_index)

    result = None
    mismatches = []
    user_grid = None

    if request.method == 'POST':
        # The form should submit 'test_index' and 'attempt' (JSON array)
        test_index = request.form.get('test_index', 0, type=int)
        attempt_text = request.form.get('attempt', '').strip()
        try:
            user_grid = json.loads(attempt_text)
        except Exception:
            user_grid = None
            result = {'ok': False, 'error': 'Invalid JSON for attempt'}

        if user_grid is not None:
            expected = task.get('test', [])[test_index].get('output')
            # simple shape check
            if not isinstance(user_grid, list) or not isinstance(expected, list):
                result = {'ok': False, 'error': 'Invalid grids'}
            else:
                # compare shapes and cells
                rows_exp = len(expected)
                cols_exp = len(expected[0]) if rows_exp else 0
                rows_usr = len(user_grid)
                cols_usr = len(user_grid[0]) if rows_usr else 0

                if rows_usr != rows_exp or cols_usr != cols_exp:
                    result = {'ok': False, 'error': 'Shape mismatch', 'expected_shape': (rows_exp, cols_exp), 'your_shape': (rows_usr, cols_usr)}
                else:
                    mismatches = []
                    for r in range(rows_exp):
                        for c in range(cols_exp):
                            if user_grid[r][c] != expected[r][c]:
                                mismatches.append([r, c])
                    result = {'ok': len(mismatches) == 0, 'mismatch_count': len(mismatches)}

    # pass absolute id if available so template can link/share
    return render_template('task.html', task=task, colors=COLORS, test_index=test_index,
                           result=result, mismatches=mismatches, user_grid=user_grid,
                           selected_concept=selected_concept, task_number=(task_id or n), task_abs_id=task_id)



@app.route('/task/compare', methods=['POST'])
def task_compare():
    """AJAX endpoint: compare a submitted grid to the expected test output and return JSON.
    Expects JSON: { id: <abs_id> (optional), n: <filtered-index> (optional), test_index: int, attempt: [[...]] }
    """
    data = request.get_json(force=True, silent=True) or request.form

    # prefer absolute id
    abs_id = None
    try:
        if isinstance(data, dict) and data.get('id') is not None:
            abs_id = int(data.get('id'))
    except Exception:
        abs_id = None

    n = None
    try:
        if isinstance(data, dict) and data.get('n') is not None:
            n = int(data.get('n'))
    except Exception:
        n = None

    test_index = 0
    try:
        test_index = int(data.get('test_index', 0))
    except Exception:
        test_index = 0

    # load task
    task = None
    if abs_id:
        task = get_task_by_id(abs_id)
    elif n:
        # no concept support for AJAX; attempt without concept
        task = get_task_by_filtered_index(None, n)

    if task is None:
        return jsonify({'ok': False, 'error': 'Task not found'}), 404

    # parse attempt
    attempt = data.get('attempt')
    if isinstance(attempt, str):
        try:
            attempt = json.loads(attempt)
        except Exception:
            attempt = None

    if not isinstance(attempt, list):
        return jsonify({'ok': False, 'error': 'Invalid attempt format'}), 400

    # get expected
    try:
        expected = task.get('test', [])[test_index].get('output')
    except Exception:
        expected = None

    if not isinstance(expected, list):
        return jsonify({'ok': False, 'error': 'No expected output for that test index'}), 400

    # compare
    rows_exp = len(expected)
    cols_exp = len(expected[0]) if rows_exp else 0
    rows_usr = len(attempt)
    cols_usr = len(attempt[0]) if rows_usr else 0

    if rows_usr != rows_exp or cols_usr != cols_exp:
        return jsonify({'ok': False, 'error': 'Shape mismatch', 'expected_shape': [rows_exp, cols_exp], 'your_shape': [rows_usr, cols_usr]}), 200

    mismatches = []
    for r in range(rows_exp):
        for c in range(cols_exp):
            if attempt[r][c] != expected[r][c]:
                mismatches.append([r, c])

    return jsonify({'ok': len(mismatches) == 0, 'mismatch_count': len(mismatches), 'mismatches': mismatches}), 200

if __name__ == '__main__':
    app.run(debug=True, port=2000)