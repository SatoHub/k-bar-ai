#!/bin/bash
set -e

echo "=== Running Alembic migrations ==="
uv run alembic upgrade head

echo "=== Starting uvicorn ==="
WORKERS="${UVICORN_WORKERS:-1}"
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "$WORKERS"
