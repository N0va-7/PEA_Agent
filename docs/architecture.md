# Architecture

## Runtime Architecture

- `frontend` calls `backend` via REST API.
- `backend` accepts `.eml` upload and creates async jobs.
- `job_runner` executes workflow graph in background thread.
- results are persisted to SQLite and markdown reports are written to disk.

## Data Locations

- DB: `runtime/db/analysis.db`
- Reports: `runtime/reports/`
- Uploads: `runtime/uploads/`
- Models: `ml/artifacts/`

## Legacy

- Old Streamlit-based agent code is archived in `legacy/agent_archive/`.
- New changes should target `backend/` + `frontend/` only.
