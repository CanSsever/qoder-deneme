.PHONY: help dev worker test coverage clean install migrate docker-up docker-down logs

# Default target
help:
	@echo "OneShot Face Swapper Backend - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  make install    - Install dependencies"
	@echo "  make dev        - Start development server with hot reload"
	@echo "  make worker     - Start Celery worker"
	@echo "  make migrate    - Run database migrations"
	@echo ""
	@echo "Testing:"
	@echo "  make test       - Run tests"
	@echo "  make test-e2e   - Run E2E tests with mock providers"
	@echo "  make coverage   - Run tests with coverage report"
	@echo "  make coverage-e2e - Run E2E tests with coverage"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up   - Start all services with Docker Compose"
	@echo "  make docker-down - Stop all Docker services"
	@echo "  make logs        - Show Docker logs"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean      - Clean cache files"

# Install dependencies
install:
	pip install -r requirements.txt

# Development server with hot reload
dev:
	@echo "Starting development server..."
	uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload --log-level info

# Start Celery worker
worker:
	@echo "Starting Celery worker..."
	celery -A apps.worker worker --loglevel=info --concurrency=2

# Run database migrations
migrate:
	@echo "Running database migrations..."
	alembic upgrade head

# Run tests
test:
	@echo "Running tests..."
	python -m pytest tests/ -v --tb=short

# Run tests with coverage
coverage:
	@echo "Running tests with coverage..."
	python -m pytest tests/ -v --cov=apps --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/"

# Run E2E tests with mock providers
test-e2e:
	@echo "Running E2E tests with mock providers..."
	python -m pytest tests/test_e2e_* -v --tb=short

# Run E2E tests with coverage
coverage-e2e:
	@echo "Running E2E tests with coverage..."
	python -m pytest tests/test_e2e_* -v --cov=apps --cov-report=html --cov-report=term-missing

# Start all services with Docker
docker-up:
	@echo "Starting all services with Docker..."
	docker-compose up -d
	@echo "Services started. API available at http://localhost:8000"
	@echo "Prometheus available at http://localhost:9090"

# Stop all Docker services
docker-down:
	@echo "Stopping all Docker services..."
	docker-compose down

# Show Docker logs
logs:
	docker-compose logs -f

# Clean cache and temporary files
clean:
	@echo "Cleaning cache files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage

# Development setup (install + migrate)
setup: install migrate
	@echo "Development setup complete!"

# Run API and worker together (for local development)
dev-full:
	@echo "Starting API and worker..."
	@echo "Note: This requires Redis to be running (use 'make docker-up' or install Redis locally)"
	@(trap 'kill 0' SIGINT; \
	 uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload & \
	 celery -A apps.worker worker --loglevel=info --concurrency=2 & \
	 wait)

# Check service health
health:
	@echo "Checking service health..."
	@curl -s http://localhost:8000/health || echo "API not responding"
	@curl -s http://localhost:8000/metrics | head -5 || echo "Metrics not available"