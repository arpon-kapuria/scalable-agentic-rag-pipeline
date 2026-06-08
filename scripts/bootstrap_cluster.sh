#!/bin/bash
set -e

CLUSTER_NAME="rag-platform-cluster"
REGION="us-east-1"

echo "🔹 1. Updating Kubeconfig..."
aws eks update-kubeconfig --name $CLUSTER_NAME --region $REGION

echo "🔹 2. Installing KubeRay Operator..."
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm repo update
helm install kuberay-operator kuberay/kuberay-operator --version 1.0.0 --wait

echo "🔹 3. Installing External Secrets Operator..."
helm repo add external-secrets https://charts.external-secrets.io
helm repo update
helm install external-secrets external-secrets/external-secrets \
    --namespace default \
    --wait

echo "   Applying ClusterSecretStore and ExternalSecret..."
kubectl apply -f deploy/secrets/cluster-secret-store.yaml
kubectl apply -f deploy/secrets/external-secrets.yaml
echo "   Waiting for secrets to sync from AWS Secrets Manager..."
sleep 15

echo "🔹 4. Installing Nginx Ingress Controller..."
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install ingress-nginx ingress-nginx/ingress-nginx \
    --namespace default \
    --wait

echo "🔹 5. Installing Vector DB (Qdrant)..."
helm install qdrant deploy/helm/qdrant \
    -f deploy/helm/qdrant/values.yaml \
    --wait

echo "🔹 6. Installing Graph DB (Neo4j)..."
helm repo add neo4j https://helm.neo4j.com/neo4j
helm repo update
helm install neo4j neo4j/neo4j \
    -f deploy/helm/neo4j/values.yaml \
    --wait

echo "🔹 7. Deploying Ray Cluster (CPU only)..."
kubectl apply -f deploy/ray/ray-cluster.yaml

echo "🔹 8. Waiting for Ray Cluster to be ready..."
sleep 30

echo "🔹 9. Deploying AI Engines..."
kubectl apply -f deploy/ray/ray-serve-llm.yaml
kubectl apply -f deploy/ray/ray-serve-embed.yaml

echo "🔹 10. Deploying API Gateway (Ingress)..."
kubectl apply -f deploy/ingress/nginx.yaml

echo "🔹 11. Deploying Backend API..."
helm install api deploy/helm/api --wait

echo "🔹 [Skipped] 12. Sandbox — enable when GPU budget available"
# kubectl apply -f deploy/sandbox/deployment.yaml
# kubectl apply -f services/sandbox/network-policy.yaml

echo "🔹 13. Installing Monitoring Stack..."
kubectl create namespace monitoring || true

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
helm repo update

helm install prometheus prometheus-community/kube-prometheus-stack \
    --namespace monitoring \
    --set grafana.adminPassword=admin123

helm install jaeger jaegertracing/jaeger \
    --namespace monitoring \
    --set allInOne.enabled=true \
    --set collector.enabled=false \
    --set agent.enabled=false \
    --set query.enabled=false

echo ""
echo "✅ Dev cluster bootstrap complete!"
echo ""
echo "⚠️  COST WARNING: This cluster costs ~\$5-7/day on AWS"
echo "   Run 'make infra-destroy' when done testing to stop charges"
echo ""
echo "📊 Monitor pods:        kubectl get pods"
echo "🌐 Get API URL:         kubectl get ingress"
echo "📈 Grafana dashboard:   kubectl port-forward svc/prometheus-grafana 3000:80 -n monitoring"
echo "🔍 Jaeger traces:       kubectl port-forward svc/jaeger-query 16686:16686 -n monitoring"
echo "💰 Monitor costs:       AWS Console → Billing → Cost Explorer"