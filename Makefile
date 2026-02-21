.PHONY: up down db-migrate db-upgrade db-downgrade ingest api dev dev-all test lint train predict verify-model evaluate scrape-shutuba scrape-odds scrape-result playwright-install

# Docker
up:
	docker compose -f docker/docker-compose.yml --env-file .env up -d

down:
	docker compose -f docker/docker-compose.yml --env-file .env down

# Database
db-migrate:
	cd backend && uv run alembic revision --autogenerate -m "$(msg)"

db-upgrade:
	cd backend && uv run alembic upgrade head

db-downgrade:
	cd backend && uv run alembic downgrade -1

# Pipeline
ingest:
	cd backend && uv run python -m app.pipeline.cli ingest --source kaggle

# ML
train:
	cd backend && uv run python -m app.pipeline.cli train --version $(version) --cutoff $(or $(cutoff),2020)

predict:
	cd backend && uv run python -m app.pipeline.cli predict --version $(version) $(if $(date),--date $(date),) $(if $(race_id),--race-id $(race_id),)

verify-model:
	cd backend && uv run python -m app.pipeline.cli verify --model-version $(version)

evaluate:
	cd backend && uv run python -m app.pipeline.cli evaluate --model-version $(version)

# Scraping
scrape-shutuba:
	cd backend && uv run python -m app.pipeline.cli scrape shutuba --date $(date)

scrape-odds:
	cd backend && uv run python -m app.pipeline.cli scrape odds --date $(date)

scrape-result:
	cd backend && uv run python -m app.pipeline.cli scrape result --date $(date)

playwright-install:
	cd backend && uv run playwright install chromium

# API (use uvicorn directly to avoid Windows emoji encoding issues with fastapi CLI)
api:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

# Data verification
verify:
	cd backend && uv run python -m scripts.verify_data

# Frontend
dev:
	cd frontend && npm run dev

# Full dev environment (Docker + Backend API + Frontend)
dev-all:
	docker compose -f docker/docker-compose.yml --env-file .env up -d
	cd backend && uv run alembic upgrade head
	@echo "Starting backend API on :8000 and frontend on :3000..."
	cd backend && uv run uvicorn app.main:app --reload --port 8000 &
	cd frontend && npm run dev &
	@echo "All services started. Backend: http://localhost:8000  Frontend: http://localhost:3000"

# Quality
test:
	cd backend && uv run pytest -v

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .

format:
	cd backend && uv run ruff check --fix . && uv run ruff format .
