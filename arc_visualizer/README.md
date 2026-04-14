# ARC Visualizer And Research Code

This folder is the pushed source-side deliverable for the ARC visualizer work.

It now includes:

- the local visualizer app and templates
- the taxonomy and dashboard builders
- the full research Python script set used during the baseline analysis

## Included Source Files

- `app.py`
- `scan_concepts.py`
- `tag_arc_tasks.py`
- `build_task_dashboard.py`
- `deterministic_arc_solver.py`
- `object_program_arc_solver.py`
- `compositional_program_search_solver.py`
- `score_submission_by_taxonomy.py`
- `summarize_kaggle_run.py`
- `templates/`

## What Stays Local

Generated outputs such as:

- taxonomy JSONL and summary files
- dashboard data JSON / JS
- local run artifacts

stay local or should be shared separately as a zip bundle / direct message payload.

## Purpose

This folder is meant to give a reviewer the actual source code behind:

- the task taxonomy split work
- the dashboard generation
- the baseline solver research tracks

without pushing the heavier generated analysis payloads.
