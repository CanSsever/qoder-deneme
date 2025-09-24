.PHONY: help dev worker test coverage clean install migrate docker-up docker-down logs deploy:staging deploy:production rollback:staging rollback:production

# Default target
help:
	@echo "OneShot Face Swapper Backend - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  make install    - Install dependencies"
	@echo "  make dev        - Start development server with hot reload"
	@echo "  make worker     - Start Celery worker"
	@echo "  make migrate    - Run database migrations"
	@echo "  make bootstrap  - Bootstrap database with default data"
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
	@echo "Deployment:"
	@echo "  make deploy:staging     - Deploy to staging environment"
	@echo "  make deploy:production  - Deploy to production environment"
	@echo "  make rollback:staging   - Rollback staging deployment"
	@echo "  make rollback:production - Rollback production deployment"
	@echo "  make smoke-test:staging - Run smoke tests against staging"
	@echo "  make smoke-test:production - Run smoke tests against production"
	@echo ""
	@echo "Monitoring:"
	@echo "  make monitor:up         - Start monitoring stack (Grafana/Prometheus/Alertmanager)"
	@echo "  make monitor:down       - Stop monitoring stack"
	@echo "  make monitor:test       - Test monitoring endpoints"
	@echo "  make monitor:setup      - Full monitoring setup"
	@echo "  make monitor:clean      - Clean monitoring data"
	@echo ""
	@echo "Data Retention:"
	@echo "  make retention:stats    - Show data retention statistics"
	@echo "  make retention:dry-run  - Run retention cleanup (dry-run, no deletion)"
	@echo "  make retention:run      - Run retention cleanup (actual deletion)"
	@echo "  make retention:custom   - Run retention with custom days"
	@echo "  make retention:test     - Run privacy and retention tests"
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

# Bootstrap database with default data
bootstrap:
	@echo "Bootstrapping database with default data..."
	python bootstrap.py

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

# =======================
# Deployment Commands
# =======================

# Deploy to staging environment
deploy:staging:
	@echo "🚀 Deploying to staging environment..."
	@if [ ! -f "deploy/staging/.env" ]; then \
		echo "❌ staging .env file not found. Copy deploy/staging/.env.example to deploy/staging/.env and configure it."; \
		exit 1; \
	fi
	@echo "🔧 Running deployment script..."
	@bash scripts/deploy.sh staging
	@echo "✅ Staging deployment completed!"

# Deploy to production environment
deploy:production:
	@echo "🚀 Deploying to production environment..."
	@echo "⚠️  This will deploy to PRODUCTION. Continue? [y/N]"
	@read -r confirm && [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ] || (echo "Deployment cancelled." && exit 1)
	@if [ ! -f "deploy/production/.env" ]; then \
		echo "❌ production .env file not found. Copy deploy/production/.env.example to deploy/production/.env and configure it."; \
		exit 1; \
	fi
	@echo "🔧 Running production deployment script..."
	@bash scripts/deploy.sh production
	@echo "✅ Production deployment completed!"

# Rollback staging deployment
rollback:staging:
	@echo "🔄 Rolling back staging deployment..."
	@bash scripts/rollback.sh staging
	@echo "✅ Staging rollback completed!"

# Rollback production deployment
rollback:production:
	@echo "🔄 Rolling back production deployment..."
	@echo "⚠️  This will rollback PRODUCTION. Continue? [y/N]"
	@read -r confirm && [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ] || (echo "Rollback cancelled." && exit 1)
	@bash scripts/rollback.sh production
	@echo "✅ Production rollback completed!"

# Run smoke tests against staging
smoke:staging:
	@echo "🧪 Running smoke tests against staging..."
	@bash scripts/smoke-test.sh --environment staging

# Run smoke tests against production
smoke:prod:
	@echo "🧪 Running smoke tests against production..."
	@bash scripts/smoke-test.sh --environment production

# Run smoke tests with bail on first failure
smoke:staging:bail:
	@echo "🧪 Running smoke tests against staging (bail on failure)..."
	@bash scripts/smoke-test.sh --environment staging --bail

smoke:prod:bail:
	@echo "🧪 Running smoke tests against production (bail on failure)..."
	@bash scripts/smoke-test.sh --environment production --bail

# Run specific smoke test scenarios
smoke:health:
	@echo "🧪 Running health check smoke tests..."
	@newman run tests/smoke/oneshot-smoke-tests.postman_collection.json \
		--folder "01. Health Checks" \
		--environment tests/smoke/environments/production.postman_environment.json \
		--reporters cli

smoke:auth:
	@echo "🧪 Running authentication smoke tests..."
	@newman run tests/smoke/oneshot-smoke-tests.postman_collection.json \
		--folder "02. Authentication" \
		--environment tests/smoke/environments/production.postman_environment.json \
		--reporters cli

smoke:security:
	@echo "🧪 Running security smoke tests..."
	@newman run tests/smoke/oneshot-smoke-tests.postman_collection.json \
		--folder "05. Security Tests" \
		--environment tests/smoke/environments/production.postman_environment.json \
		--reporters cli

# Windows PowerShell versions of smoke tests
smoke-test:staging:ps:
	@echo "🧪 Running smoke tests against staging (PowerShell)..."
	powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1 -BaseUrl "https://staging.yourdomain.com"

smoke-test:production:ps:
	@echo "🧪 Running smoke tests against production (PowerShell)..."
	powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1 -BaseUrl "https://api.yourdomain.com"

# Full deployment with smoke tests
deploy:staging:full: deploy:staging smoke:staging
deploy:production:full: deploy:production smoke:prod

# Quick deployment status check
deploy:status:
	@echo "📊 Deployment Status:"
	@echo "============================="
	@if [ -f ".last-deployment-staging" ]; then \
		echo "Staging - Last Deployment: $$(cat .last-deployment-staging) at $$(cat .last-deployment-time-staging 2>/dev/null || echo 'Unknown time')"; \
	else \
		echo "Staging - No deployments recorded"; \
	fi
	@if [ -f ".last-deployment-production" ]; then \
		echo "Production - Last Deployment: $$(cat .last-deployment-production) at $$(cat .last-deployment-time-production 2>/dev/null || echo 'Unknown time')"; \
	else \
		echo "Production - No deployments recorded"; \
	fi
	@if [ -f ".last-rollback-staging" ]; then \
		echo "Staging - Last Rollback: $$(cat .last-rollback-staging) at $$(cat .last-rollback-time-staging 2>/dev/null || echo 'Unknown time')"; \
	fi
	@if [ -f ".last-rollback-production" ]; then \
		echo "Production - Last Rollback: $$(cat .last-rollback-production) at $$(cat .last-rollback-time-production 2>/dev/null || echo 'Unknown time')"; \
	fi

# =======================
# Monitoring Commands
# =======================

# Start monitoring stack
monitor:up:
	@echo "📊 Starting monitoring stack..."
	docker-compose -f docker-compose.monitoring.yml up -d
	@echo "✅ Monitoring stack started!"
	@echo "Grafana: http://localhost:3000 (admin/admin123)"
	@echo "Prometheus: http://localhost:9090"
	@echo "Alertmanager: http://localhost:9093"

# Stop monitoring stack
monitor:down:
	@echo "📊 Stopping monitoring stack..."
	docker-compose -f docker-compose.monitoring.yml down
	@echo "✅ Monitoring stack stopped!"

# View monitoring logs
monitor:logs:
	@echo "📊 Monitoring stack logs:"
	docker-compose -f docker-compose.monitoring.yml logs -f

# Test monitoring setup
monitor:test:
	@echo "🧪 Testing monitoring endpoints..."
	@curl -f http://localhost:8000/metrics > /dev/null && echo "✅ API metrics endpoint working" || echo "❌ API metrics endpoint failed"
	@curl -f http://localhost:8000/healthz > /dev/null && echo "✅ API health endpoint working" || echo "❌ API health endpoint failed"
	@curl -f http://localhost:8000/readyz > /dev/null && echo "✅ API readiness endpoint working" || echo "❌ API readiness endpoint failed"
	@curl -f http://localhost:9090/-/healthy > /dev/null && echo "✅ Prometheus healthy" || echo "❌ Prometheus not healthy"
	@curl -f http://localhost:9093/-/healthy > /dev/null && echo "✅ Alertmanager healthy" || echo "❌ Alertmanager not healthy"
	@curl -f http://localhost:3000/api/health > /dev/null && echo "✅ Grafana healthy" || echo "❌ Grafana not healthy"

# Generate test alerts (dry-run)
monitor:test-alerts:
	@echo "😨 Generating test alerts (dry-run mode)..."
	python -c "from tests.test_monitoring import generate_test_alerts; generate_test_alerts()"

# Full monitoring setup
monitor:setup:
	@echo "📊 Setting up complete monitoring stack..."
	make monitor:up
	@echo "Waiting for services to start..."
	sleep 30
	make monitor:test
	@echo "✅ Monitoring setup complete!"

# Monitor cleanup
monitor:clean:
	@echo "🧹 Cleaning monitoring data..."
	docker-compose -f docker-compose.monitoring.yml down -v
	@echo "✅ Monitoring data cleaned!"

# =======================
# Data Retention Commands
# =======================

# Run data retention cleanup (dry-run)
retention:dry-run:
	@echo "🧹 Running data retention cleanup (dry-run)..."
	python -c "from apps.core.privacy import DataRetentionService; import json; service = DataRetentionService(); result = service.run_retention_cleanup(dry_run=True); print(json.dumps(result, indent=2))"

# Run data retention cleanup (actual deletion)
retention:run:
	@echo "🧹 Running data retention cleanup..."
	@echo "⚠️  This will permanently delete old data. Continue? [y/N]"
	@read -r confirm && [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ] || (echo "Cleanup cancelled." && exit 1)
	python -c "from apps.core.privacy import DataRetentionService; import json; service = DataRetentionService(); result = service.run_retention_cleanup(dry_run=False); print(json.dumps(result, indent=2))"

# Get retention statistics
retention:stats:
	@echo "📊 Getting data retention statistics..."
	python -c "from apps.core.privacy import DataRetentionService; import json; service = DataRetentionService(); stats = service.get_retention_stats(); print(json.dumps(stats, indent=2))"

# Run retention with custom days
retention:custom:
	@echo "🧹 Running data retention with custom retention period..."
	@echo "Enter retention days (default 30): "; \
	read -r days; \
	days=$${days:-30}; \
	echo "Using $$days days retention period"; \
	python -c "from apps.core.privacy import DataRetentionService; import json; service = DataRetentionService(retention_days=$$days); result = service.run_retention_cleanup(dry_run=True); print(json.dumps(result, indent=2))"

# Privacy test suite
retention:test:
	@echo "🧪 Running privacy and retention tests..."
	python -m pytest tests/test_privacy_safety.py -v --tb=short