# bridge/web — control UI (FastAPI)

## Purpose

The local management surface on port 7860: a first-run setup wizard (detect/install ComfyUI,
enter grid key + models) and a dashboard to view worker status and edit settings. It also
owns the worker lifecycle.

## Ownership

- `app.py` — the FastAPI app, lifespan, and `worker_state` (running/error/task/bridge).
  `_run_worker` selects WS vs legacy transport by `Settings.GRID_WS`; `start_worker`/`stop_worker`
  manage the background task.
- `routes.py` — HTTP routes + JSON `/api/*` endpoints (setup detect/install/check/complete,
  status, settings save, worker restart) and the `setup_guard` redirect middleware. Reads/writes
  `.env` and mutates `Settings` in place.
- `templates/` — Jinja2 pages (base, setup, dashboard, settings). `static/` — CSS.

## Local Contracts

- This is the only place that persists config: it writes `.env` and updates `Settings`
  attributes live. Config still flows through `Settings`; do not read env here directly.
- Settings changes apply to the in-memory `Settings` immediately but a worker restart
  (`/api/worker/restart`) is required for the worker to pick them up.
- This UI binds `0.0.0.0:7860` with no auth — it is a local/trusted-network control panel,
  not a public endpoint.

## Work Guidance

—

## Verification

—

## Child DOX Index

- None — leaf.
