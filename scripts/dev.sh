#!/bin/bash
# Start the backend and the frontend together for local development.
# Usage (from the repo root): ./scripts/dev.sh   — press Ctrl+C once to stop both.
set -e
cd "$(dirname "$0")/.."

trap 'kill 0' EXIT  # stop everything this script started

(
  cd backend
  source .venv/bin/activate
  uvicorn app.main:app --reload --port 8000
) &

cd frontend
npm run dev
