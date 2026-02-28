#!/bin/bash
set -e

echo "=== Running Alembic migrations ==="
uv run alembic upgrade head

echo "=== Checking ML model files ==="
MODEL_DIR="/app/models"
if [ ! -d "$MODEL_DIR" ] || [ -z "$(ls -A "$MODEL_DIR"/*.joblib 2>/dev/null)" ]; then
    echo "WARNING: No model files found in $MODEL_DIR"
    echo "WARNING: AI predictions will fail until a .joblib model is deployed."
    echo "WARNING: Copy model file: docker cp v1.0.0.joblib kbar-backend:/app/models/"
else
    echo "Found model files:"
    ls -lh "$MODEL_DIR"/*.joblib
fi

echo "=== Starting uvicorn ==="
WORKERS="${UVICORN_WORKERS:-1}"
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "$WORKERS"
