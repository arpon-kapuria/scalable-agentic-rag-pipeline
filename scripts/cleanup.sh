#!/bin/bash

echo "⚠️  WARNING: THIS WILL DESTROY ALL CLOUD RESOURCES ⚠️"
echo "Includes: EKS Cluster, Databases (RDS/Neo4j/Redis), S3 Buckets, Load Balancers."
echo "Cost-saving measure for Dev/Test environments."
echo ""
read -p "Are you sure? Type 'DESTROY': " confirm

if [ "$confirm" != "DESTROY" ]; then
    echo "Aborted."
    exit 1
fi

echo "🔹 1. Deleting Kubernetes Resources (Helm)..."
helm uninstall api || true
helm uninstall qdrant || true
helm uninstall ray-cluster || true
kubectl delete -f deploy/ray/ || true

echo "🔹 2. Waiting for LBs to cleanup..."
sleep 20

echo "🔹 3. Running Terraform Destroy..."
cd infra/terraform
terraform destroy -auto-approve

echo "✅ All resources destroyed."