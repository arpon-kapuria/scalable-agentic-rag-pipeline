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
# 8GB RAM dev box: never bring up the full stack. Usage: make up PROFILE=core
# See PROJECT_INSTRUCTIONS.md's profile table for which profiles a given phase needs.
up:
	ifndef PROFILE
		$(error PROFILE is required, e.g. make up PROFILE=core (see PROJECT_INSTRUCTIONS.md profile table))
	endif
		docker compose --profile $(PROFILE) up -d

down:
	ifndef PROFILE
		docker compose down
	else
		docker compose --profile $(PROFILE) down
	endif

# Run the API locally (Hot Reload)
dev:
	uv run uvicorn services.api.main:app --reload --host 0.0.0.0 --port 8000 --env-file .env

# Infrastructure (Terraform)
infra:
	cd infra/terraform && terraform init && terraform apply

# Kubernetes Deployment (Helm)
deploy:
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