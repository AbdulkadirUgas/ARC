# ARC Visualizer Source

This folder contains the source-side visualizer and taxonomy/dashboard builder code.

It is intended to be pushed without large generated JSON artifacts.

## Included

- `app.py`
- `scan_concepts.py`
- `tag_arc_tasks.py`
- `build_task_dashboard.py`
- `templates/`

## What Stays Local

Generated outputs such as:

- taxonomy JSONL and summary files
- dashboard data JSON / JS
- local run artifacts

should stay local or be shared separately as a zip bundle or direct message payload.

## Typical Flow

1. Run `tag_arc_tasks.py` to build the task taxonomy.
2. Run `build_task_dashboard.py` to generate dashboard-ready data locally.
3. Use the templates and app code here to serve or adapt the visualizer.

## Notes

- `templates/task_dashboard_source.html` is the richer local dashboard source template.
- The lightweight public Pages site is in `docs/`, but the generated publish JSON is intentionally not the main source deliverable here.
