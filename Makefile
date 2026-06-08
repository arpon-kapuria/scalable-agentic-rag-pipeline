.PHONY: help install dev up down deploy infra test lint fmt docker docker-login docker-build docker-tag docker-push ecr-setup infra-destroy

# ─── Config ────────────────────────────────────────────────────────────────────
AWS_REGION  := us-east-1
AWS_ACCOUNT := $(shell aws sts get-caller-identity --query Account --output text)
ECR_BASE    := $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com

# Pull ECR URLs from Terraform output instead of hardcoding
ECR_API_URL   := $(shell cd infra/terraform && terraform output -raw ecr_api_url 2>/dev/null)
ECR_MODEL_URL := $(shell cd infra/terraform && terraform output -raw ecr_models_url 2>/dev/null)

# SANDBOX 
# SANDBOX_IMAGE := $(ECR_SANDBOX_URL):latest
# ECR_SANDBOX_URL := $(shell cd infra/terraform && terraform output -raw ecr_sandbox_url 2>/dev/null)

# ─── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  RAG Platform Commands"
	@echo "  ─────────────────────────────────────────────"
	@echo "  Local Development"
	@echo "    make install       Install Python dependencies"
	@echo "    make up            Start local DBs via Docker Compose"
	@echo "    make down          Stop local DBs"
	@echo "    make dev           Run FastAPI locally with hot reload"
	@echo "    make lint          Run ruff linter"
	@echo "    make fmt           Format code with ruff"
	@echo "    make test          Run test suite"
	@echo ""
	@echo "  AWS Infrastructure"
	@echo "    make infra         Provision AWS infrastructure via Terraform"
	@echo "    make infra-destroy Tear down all AWS infrastructure"
	@echo ""
	@echo "  Docker"
	@echo "    make docker        Build, tag and push all images to ECR"
	@echo ""
	@echo "  Deployment"
	@echo "    make bootstrap     Bootstrap EKS cluster (operators + app)"
	@echo "    make deploy        Deploy/upgrade application via Helm"
	@echo "  ─────────────────────────────────────────────"
	@echo ""

# ─── Local Development ─────────────────────────────────────────────────────────
install:
	uv sync --group api --group dev

up:
	docker compose up -d

down:
	docker compose down

dev:
	uv run uvicorn services.api.main:app --reload --host 0.0.0.0 --port 8000 --env-file .env

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

test:
	uv run pytest tests/ -v

# ─── Infrastructure ────────────────────────────────────────────────────────────
infra:
	cd infra/terraform && terraform init && terraform apply

infra-destroy:
	./scripts/cleanup.sh

# ─── Docker ────────────────────────────────────────────────────────────────────
docker-login:
	aws ecr get-login-password --region $(AWS_REGION) | \
	docker login --username AWS --password-stdin $(ECR_BASE)

docker-build:
	@echo "🔨 Building API image..."
	docker build -t rag-api -f services/api/Dockerfile .
	@echo "🔨 Building Models image..."
	docker build --build-arg MODE=minimal -t rag-models -f services/api/app/models/Dockerfile .
# 	@echo "🔨 Building Sandbox image..."
# 	docker build -t rag-sandbox -f services/sandbox/Dockerfile .

docker-tag:
	docker tag rag-api $(ECR_API_URL):latest
	docker tag rag-models $(ECR_MODEL_URL):latest
# 	docker tag rag-sandbox $(ECR_SANDBOX_URL):latest

docker-push:
	docker push $(ECR_API_URL):latest
	docker push $(ECR_MODEL_URL):latest
# 	docker push $(ECR_SANDBOX_URL):latest

# Build + tag + push in one command
docker: docker-login docker-build docker-tag docker-push
	@echo "✅ All images pushed to ECR"

# ─── Deployment ────────────────────────────────────────────────────────────────
bootstrap:
	./scripts/bootstrap_cluster.sh

deploy:
	helm dependency update deploy/helm/api
	helm upgrade --install api deploy/helm/api \
		--namespace default \
		--set image.repository=$(ECR_API_URL) \
		--set image.tag=latest
	helm upgrade --install ray-cluster kuberay/ray-cluster \
		-f deploy/ray/ray-cluster.yaml

# ─── Full flow shortcuts ────────────────────────────────────────────────────────
# First time setup: make infra → make docker → make bootstrap
# Subsequent deploys: make docker → make deploy