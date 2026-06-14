.PHONY: up down logs migrate seed eval eval-raw eval-cleaned eval-report test lint format install-api install-web run

run:
	./dev.sh

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build

migrate:
	docker compose exec api alembic upgrade head

makemigration:
	docker compose exec api alembic revision --autogenerate -m "$(msg)"

seed:
	docker compose exec api python -m pipelines.ingestion.seed_loader

eval-raw:
	docker compose exec api python -m pipelines.eval.harness --mode raw

eval-cleaned:
	docker compose exec api python -m pipelines.eval.harness --mode cleaned

eval:
	@echo "=== RAW baseline ===" && make eval-raw
	@echo ""
	@echo "=== CLEANED pipeline ===" && make eval-cleaned

eval-report:
	@echo "=== Running harness (both modes) ==="
	# Write JSON to /data (mounted to ./data on the host) so the host can read it.
	docker compose exec api python -m pipelines.eval.harness --mode both --output /data/results.json
	@echo "=== Injecting results into README ==="
	# report.py is pure file I/O; run on the HOST so it can edit ./README.md
	# (the repo root is not mounted into the api container).
	python -m pipelines.eval.report --input data/results.json --readme README.md

test:
	cd apps/api && python -m pytest ../../tests/ -v

lint:
	cd apps/api && python -m ruff check .
	cd apps/api && python -m ruff format --check .

format:
	cd apps/api && python -m ruff check --fix .
	cd apps/api && python -m ruff format .

install-api:
	cd apps/api && pip install -r requirements.txt

install-web:
	cd apps/web && npm install

shell-api:
	docker compose exec api bash

shell-db:
	docker compose exec postgres psql -U kortex kortex
