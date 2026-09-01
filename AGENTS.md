# NER Risk Monitor — Agent Instructions

## Workflow

- Work is tracked as tickets in `.scratch/` (local file tracker).
- After completing each ticket: commit to `main` and push to the GitHub remote.
- Backend tests: `python -m pytest backend/tests` (run from repo root).
- Frontend type checks: `npx tsc --noEmit` (run from `frontend/`).
- Frontend build: `npm run build` (run from `frontend/`).

## Stack

- Backend: FastAPI + SQLite (`backend/`), run with `uvicorn backend.main:app --reload --port 8000` from repo root.
- Frontend: Next.js App Router (`frontend/`), run with `npm run dev`.
- Risk model and thresholds are defined in the spec; `backend/risk_engine.py` is the single source of truth.
