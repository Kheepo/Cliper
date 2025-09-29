# Makefile for Cliper - AI-Powered Video Clip Generation System
# Provides convenient commands for development, testing, and deployment

.PHONY: help install install-dev setup clean test test-unit test-integration test-e2e
.PHONY: lint format type-check security-check
.PHONY: dev dev-api dev-worker dev-frontend
.PHONY: build build-dev build-prod
.PHONY: deploy deploy-dev deploy-staging deploy-prod
.PHONY: logs logs-api logs-worker logs-all
.PHONY: db-migrate db-reset db-seed
.PHONY: docker-build docker-up docker-down docker-clean
.PHONY: backup restore monitoring

# Default target
help: ## Show this help message
	@echo "Cliper - AI-Powered Video Clip Generation System"
	@echo "================================================"
	@echo ""
	@echo "Available commands:"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

# Installation and Setup
install: ## Install production dependencies
	pip install -r requirements.txt
	npm install --production

install-dev: ## Install development dependencies
	pip install -r requirements-dev.txt
	npm install
	pre-commit install

setup: install-dev ## Setup development environment
	cp .env.example .env
	@echo "Please edit .env file with your configuration"
	@echo "Then run 'make db-migrate' to setup database"

clean: ## Clean temporary files and caches
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type f -name ".coverage" -delete
	rm -rf dist/ build/ *.egg-info/
	rm -rf node_modules/.cache/
	rm -rf logs/*.log
	rm -rf tmp/*

# Testing
test: ## Run all tests
	python run_tests.py

test-unit: ## Run unit tests only
	python run_tests.py --unit

test-integration: ## Run integration tests only
	python run_tests.py --integration

test-e2e: ## Run end-to-end tests only
	python run_tests.py --e2e

test-coverage: ## Run tests with coverage report
	python run_tests.py --coverage --html-report

test-parallel: ## Run tests in parallel
	python run_tests.py --parallel

test-watch: ## Run tests in watch mode
	ptw --runner "python run_tests.py"

# Code Quality
lint: ## Run linting checks
	flake8 api/ tests/
	pylint api/ tests/
	eslint src/

format: ## Format code
	black api/ tests/
	isort api/ tests/
	prettier --write src/

type-check: ## Run type checking
	mypy api/
	npm run type-check

security-check: ## Run security checks
	bandit -r api/
	safety check
	npm audit

# Development
dev: ## Start all development services
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
	@echo "Services started:"
	@echo "  - API: http://localhost:8000"
	@echo "  - Frontend: http://localhost:3000"
	@echo "  - Flower: http://localhost:5555"
	@echo "  - Redis: localhost:6379"

dev-api: ## Start API development server
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

dev-worker: ## Start Celery worker
	celery -A api.tasks.celery_app worker --loglevel=info --reload

dev-beat: ## Start Celery beat scheduler
	celery -A api.tasks.celery_app beat --loglevel=info

dev-frontend: ## Start frontend development server
	npm run dev

dev-stop: ## Stop development services
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml down

# Building
build: ## Build production images
	docker-compose build

build-dev: ## Build development images
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml build

build-prod: ## Build production images with optimizations
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache

build-frontend: ## Build frontend for production
	npm run build

# Deployment
deploy: ## Deploy to production
	python deploy.py

deploy-dev: ## Deploy to development environment
	ENVIRONMENT=development python deploy.py --config deployment.yml

deploy-staging: ## Deploy to staging environment
	ENVIRONMENT=staging python deploy.py --config deployment.yml

deploy-prod: ## Deploy to production environment
	ENVIRONMENT=production python deploy.py --config deployment.yml

validate-env: ## Validate deployment environment
	python deploy.py --validate-only

rollback: ## Rollback to previous deployment
	@read -p "Enter backup path: " backup_path; \
	python deploy.py --rollback $$backup_path

# Logging
logs: ## Show application logs
	docker-compose logs -f app

logs-api: ## Show API logs
	docker-compose logs -f app

logs-worker: ## Show worker logs
	docker-compose logs -f worker

logs-all: ## Show all service logs
	docker-compose logs -f

logs-errors: ## Show error logs only
	docker-compose logs -f | grep -i error

# Database
db-migrate: ## Run database migrations
	alembic upgrade head

db-reset: ## Reset database (WARNING: destroys data)
	@read -p "Are you sure you want to reset the database? [y/N] " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		alembic downgrade base; \
		alembic upgrade head; \
	else \
		echo "Database reset cancelled."; \
	fi

db-seed: ## Seed database with sample data
	python scripts/seed_database.py

db-backup: ## Create database backup
	python scripts/backup_database.py

db-restore: ## Restore database from backup
	@read -p "Enter backup file path: " backup_file; \
	python scripts/restore_database.py $$backup_file

# Docker Management
docker-build: build ## Build Docker images

docker-up: ## Start Docker services
	docker-compose up -d

docker-down: ## Stop Docker services
	docker-compose down

docker-restart: ## Restart Docker services
	docker-compose restart

docker-clean: ## Clean Docker resources
	docker-compose down -v --remove-orphans
	docker system prune -f
	docker volume prune -f

docker-logs: logs-all ## Show Docker logs

docker-ps: ## Show running containers
	docker-compose ps

docker-stats: ## Show container resource usage
	docker stats

# Monitoring and Health
health: ## Check service health
	@echo "Checking service health..."
	@curl -s http://localhost:8000/health | jq .
	@echo ""
	@curl -s http://localhost:8000/api/v1/health | jq .

monitoring: ## Open monitoring dashboards
	@echo "Opening monitoring dashboards..."
	@echo "Prometheus: http://localhost:9090"
	@echo "Grafana: http://localhost:3000 (admin/admin)"
	@echo "Flower: http://localhost:5555"
	@if command -v open >/dev/null 2>&1; then \
		open http://localhost:9090; \
		open http://localhost:3000; \
		open http://localhost:5555; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open http://localhost:9090; \
		xdg-open http://localhost:3000; \
		xdg-open http://localhost:5555; \
	fi

status: ## Show service status
	@echo "Service Status:"
	@echo "=============="
	docker-compose ps
	@echo ""
	@echo "Health Checks:"
	@echo "=============="
	@curl -s http://localhost:8000/health 2>/dev/null | jq -r '.status // "Service not available"' || echo "API: Not available"
	@redis-cli ping 2>/dev/null || echo "Redis: Not available"

# Backup and Restore
backup: ## Create full system backup
	@echo "Creating system backup..."
	mkdir -p backups/$(shell date +%Y%m%d_%H%M%S)
	cp .env backups/$(shell date +%Y%m%d_%H%M%S)/
	cp docker-compose.yml backups/$(shell date +%Y%m%d_%H%M%S)/
	make db-backup
	@echo "Backup completed: backups/$(shell date +%Y%m%d_%H%M%S)"

restore: ## Restore from backup
	@read -p "Enter backup directory: " backup_dir; \
	if [ -d "$$backup_dir" ]; then \
		cp $$backup_dir/.env .; \
		cp $$backup_dir/docker-compose.yml .; \
		echo "Configuration restored from $$backup_dir"; \
	else \
		echo "Backup directory not found: $$backup_dir"; \
	fi

# Performance and Optimization
optimize: ## Run performance optimizations
	@echo "Running performance optimizations..."
	make clean
	docker system prune -f
	pip install --upgrade pip
	npm update
	@echo "Optimization completed"

profile: ## Profile application performance
	py-spy record -o profile.svg -d 60 -s -- python -m uvicorn api.main:app
	@echo "Profile saved to profile.svg"

benchmark: ## Run performance benchmarks
	@echo "Running performance benchmarks..."
	locust -f tests/performance/locustfile.py --headless -u 10 -r 2 -t 60s --host http://localhost:8000

# Security
security-scan: ## Run comprehensive security scan
	@echo "Running security scans..."
	make security-check
	docker run --rm -v $(PWD):/app clair-scanner:latest
	@echo "Security scan completed"

ssl-setup: ## Setup SSL certificates
	@echo "Setting up SSL certificates..."
	mkdir -p ssl
	openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes
	@echo "SSL certificates created in ssl/ directory"

# Utilities
shell: ## Open Python shell with app context
	python -c "from api.main import app; import IPython; IPython.embed()"

db-shell: ## Open database shell
	psql $(DATABASE_URL)

redis-shell: ## Open Redis shell
	redis-cli

generate-secret: ## Generate secret key
	@python -c "import secrets; print(secrets.token_urlsafe(32))"

update-deps: ## Update dependencies
	pip-compile requirements.in
	pip-compile requirements-dev.in
	npm update

# Documentation
docs: ## Generate documentation
	sphinx-build -b html docs/ docs/_build/html/
	@echo "Documentation generated in docs/_build/html/"

docs-serve: ## Serve documentation locally
	cd docs/_build/html && python -m http.server 8080

api-docs: ## Generate API documentation
	python scripts/generate_api_docs.py

# CI/CD
ci-test: ## Run CI test suite
	make lint
	make type-check
	make security-check
	make test-coverage

ci-build: ## Build for CI
	make build-prod

ci-deploy: ## Deploy from CI
	make deploy-prod

# Quick Commands
quick-start: setup dev ## Quick start for new developers
	@echo "Quick start completed!"
	@echo "Edit .env file and run 'make db-migrate' to finish setup"

quick-test: lint test-unit ## Quick test for development

quick-deploy: test deploy ## Quick deploy with tests

# Environment Info
info: ## Show environment information
	@echo "Environment Information:"
	@echo "======================"
	@echo "Python: $(shell python --version)"
	@echo "Node.js: $(shell node --version)"
	@echo "Docker: $(shell docker --version)"
	@echo "Docker Compose: $(shell docker-compose --version)"
	@echo "Git: $(shell git --version)"
	@echo ""
	@echo "Project Status:"
	@echo "=============="
	@echo "Environment: $(shell grep ENVIRONMENT .env 2>/dev/null | cut -d= -f2 || echo 'Not configured')"
	@echo "Debug Mode: $(shell grep DEBUG .env 2>/dev/null | cut -d= -f2 || echo 'Not configured')"
	@echo "Database: $(shell grep SUPABASE_URL .env 2>/dev/null | cut -d= -f2 | cut -c1-20 || echo 'Not configured')..."
	@echo "Redis: $(shell grep REDIS_URL .env 2>/dev/null | cut -d= -f2 || echo 'Not configured')"

# Default target when no arguments provided
.DEFAULT_GOAL := help