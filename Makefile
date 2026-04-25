.PHONY: help install dev up down deploy infra test

help:
	@echo "	 RAG Platform Commands:"
	@echo "  Usage: make <target>"
	@echo "  make install    - Install Python dependencies"
	@echo "  make up         - Start local DBs (Docker)"
	@echo "  make down       - Stop local DBs"
	@echo "  make dev        - Run FastAPI server locally"
	@echo "  make infra      - Apply Terraform"
	@echo "  make deploy     - Deploy to AWS EKS via Helm"
	@echo "  lint          	 - Run ruff linter"
	@echo "  fmt             - Format code with ruff"
	@echo "  test            - Run test suite"

# Install dependencies using uv
install:
	uv sync --group api --group dev

# Run Local Development Environment (Docker services)
up:
	docker compose up -d

down:
	docker compose down

# Run the API locally (Hot Reload)
dev:
	uv run uvicorn services.api.main:app --reload --host 0.0.0.0 --port 8000 --env-file .env

# Ray requirements export for Ingestion
ray-reqs:
	uv export --frozen --only-group ingestion -o pipelines/jobs/requirements-ray.txt
	@echo "  ✓ pipelines/jobs/requirements-ray.txt updated"

# Infrastructure (Terraform)
infra:
	cd infra/terraform && terraform init && terraform apply

# Kubernetes Deployment (Helm)
deploy: ray-reqs
	# Update dependencies
	helm dependency update deploy/helm/api

	# Install/Upgrade
	helm upgrade --install api deploy/helm/api --namespace default
	helm upgrade --install ray-cluster kuberay/ray-cluster -f deploy/ray/ray-cluster.yaml

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

test:
	uv run pytest tests/ -v