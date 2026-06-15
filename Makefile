.PHONY: help setup build up down logs test lint format clean

help:
	@echo "BidPilot AI - Development Commands"
	@echo "=================================="
	@echo "make setup      - Setup development environment"
	@echo "make build      - Build Docker images"
	@echo "make up         - Start all services"
	@echo "make down       - Stop all services"
	@echo "make logs       - View service logs"
	@echo "make test       - Run tests"
	@echo "make lint       - Run linter"
	@echo "make format     - Format code"
	@echo "make migrate    - Run database migrations"
	@echo "make clean      - Clean up containers and volumes"

setup:
	@echo "Setting up development environment..."
	cp .env.example .env
	cd backend && python -m venv venv
	cd frontend && npm install
	@echo "✓ Setup complete. Edit .env and run 'make up'"

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "✓ Services running"
	@echo "  Backend:  http://localhost:8000"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Flower:   http://localhost:5555"

down:
	docker-compose down

logs:
	docker-compose logs -f

logs-backend:
	docker-compose logs -f backend

logs-worker:
	docker-compose logs -f celery-worker

test:
	cd backend && pytest tests/ -v

lint:
	cd backend && flake8 app/
	cd frontend && npm run lint

format:
	cd backend && black app/
	cd frontend && prettier --write .

migrate:
	docker-compose exec backend alembic upgrade head

migrate-rollback:
	docker-compose exec backend alembic downgrade -1

migrate-create:
	docker-compose exec backend alembic revision --autogenerate -m "$(message)"

clean:
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf backend/.coverage
	rm -rf frontend/.next
	@echo "✓ Cleaned up"

shell-backend:
	docker-compose exec backend bash

shell-postgres:
	docker-compose exec postgres psql -U bidpilot -d bidpilot
