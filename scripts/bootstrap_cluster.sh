#!/bin/bash
# scripts/bootstrap_cluster.sh

set -e # Exit on error

CLUSTER_NAME="rag-platform-cluster"
REGION="us-east-1"

echo "🔹 1. Updating Kubeconfig..."
aws eks update-kubeconfig --name $CLUSTER_NAME --region $REGION

echo "🔹 2. Installing KubeRay Operator..."
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm repo update
helm install kuberay-operator kuberay/kuberay-operator --version 1.0.0

echo "🔹 3. Installing Vector DB (Qdrant)..."
helm install qdrant deploy/helm/qdrant -f deploy/helm/qdrant/values.yaml

echo "🔹 4. Deploying Ray Cluster (This spawns the Head Node)..."
kubectl apply -f deploy/ray/ray-cluster.yaml

echo "🔹 5. Waiting for Ray Cluster to be ready..."
sleep 30

echo "🔹 6. Deploying AI Engines (vLLM & Embeddings)..."
# These trigger Karpenter to buy GPUs
kubectl apply -f deploy/ray/ray-serve-llm.yaml
kubectl apply -f deploy/ray/ray-serve-embed.yaml

echo "🔹 7. Deploying API Gateway (Ingress)..."
kubectl apply -f deploy/ingress/nginx.yaml

echo "🔹 8. Deploying Backend API..."
helm install api deploy/helm/api

echo "✅ Cluster Bootstrap Complete! Monitor pods with: kubectl get pods"